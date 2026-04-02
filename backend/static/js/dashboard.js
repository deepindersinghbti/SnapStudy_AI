import {
    clearToken,
    formatTimestamp,
    log,
    markdownToHtml,
    redirect,
    requestAuthJson,
    setLoading,
    showToast,
    validateSession,
} from "/static/js/utils.js";

const gate = document.getElementById("dashboard-gate");
const dashboardContent = document.getElementById("dashboard-content");
const authStatus = document.getElementById("auth-status");
const uploadForm = document.getElementById("upload-form");
const uploadBtn = document.getElementById("upload-btn");
const refreshBtn = document.getElementById("refresh-btn");
const logoutBtn = document.getElementById("logout-btn");
const uploadsList = document.getElementById("uploads-list");
const statusLog = document.getElementById("status-log");

function resolveProcessingState(row) {
    return row.processing_state || (row.extracted_text ? "success" : "failure");
}

function stateBadgeLabel(state) {
    if (state === "partial") {
        return "Partial";
    }
    if (state === "failure") {
        return "Failed";
    }
    return "Success";
}

function stateToastKind(state) {
    if (state === "failure") {
        return "error";
    }
    if (state === "partial") {
        return "info";
    }
    return "success";
}

function createFollowupMessageNode(message) {
    const wrapper = document.createElement("article");
    wrapper.className = "followup-message";

    const question = document.createElement("p");
    question.className = "followup-question";
    question.innerHTML = `Q: ${markdownToHtml(message.question || "")}`;

    const answer = document.createElement("p");
    answer.className = "followup-answer";
    answer.innerHTML = `A: ${markdownToHtml(message.response || "")}`;

    wrapper.appendChild(question);
    wrapper.appendChild(answer);
    return wrapper;
}

function renderFollowupMessages(threadEl, messages) {
    threadEl.innerHTML = "";
    if (!Array.isArray(messages) || messages.length === 0) {
        threadEl.innerHTML = '<p class="followup-empty">No follow-up questions yet.</p>';
        return;
    }

    for (const message of messages) {
        threadEl.appendChild(createFollowupMessageNode(message));
    }
    threadEl.scrollTop = threadEl.scrollHeight;
}

async function loadFollowupMessages(uploadId, threadEl, errorEl) {
    errorEl.textContent = "";
    const data = await requestAuthJson(`/uploads/${uploadId}/followups`);
    renderFollowupMessages(threadEl, data.messages || []);
}

async function submitFollowup(uploadId, question, threadEl, errorEl) {
    const data = await requestAuthJson(`/uploads/${uploadId}/followups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
    });

    const emptyEl = threadEl.querySelector(".followup-empty");
    if (emptyEl) {
        emptyEl.remove();
    }
    threadEl.appendChild(createFollowupMessageNode({ question: data.question, response: data.response }));
    threadEl.scrollTop = threadEl.scrollHeight;
    errorEl.textContent = "";
}

function renderEmptyUploadsState() {
    uploadsList.innerHTML = `
    <article class="empty-state">
      <h3>No uploads yet</h3>
      <p>Upload your first image or PDF note to generate OCR text and an AI explanation.</p>
    </article>
  `;
}

async function loadUploads() {
    const data = await requestAuthJson("/uploads");
    uploadsList.innerHTML = "";

    if (!Array.isArray(data) || data.length === 0) {
        renderEmptyUploadsState();
        log(statusLog, "No uploads found for this account.");
        return;
    }

        for (const row of data) {
                const processingState = resolveProcessingState(row);
                const processingNote = row.processing_note || "";
        const item = document.createElement("article");
                item.className = `upload-item state-${processingState}`;
        item.innerHTML = `
            <p class="upload-meta"><strong>ID:</strong> ${row.id} | <strong>Type:</strong> ${row.file_type} | <strong>Created:</strong> ${formatTimestamp(row.created_at)} | <strong>Status:</strong> <span class="upload-state ${processingState}">${stateBadgeLabel(processingState)}</span></p>
            ${processingNote ? `<p class="processing-note">${processingNote}</p>` : ""}
      <p class="upload-block"><strong>Extracted Text</strong><br>${markdownToHtml(row.extracted_text || "(empty)")}</p>
      <p class="upload-block"><strong>Explanation</strong><br>${markdownToHtml(row.explanation || "(empty)")}</p>
      <div class="followup-wrap">
        <button type="button" class="secondary followup-toggle">Show Follow-Up</button>
        <div class="followup-panel hidden">
          <div class="followup-thread"><p class="followup-empty">No follow-up questions yet.</p></div>
          <p class="followup-error" aria-live="polite"></p>
          <form class="followup-form">
            <input type="text" class="followup-input" maxlength="2000" placeholder="Ask a follow-up question" required>
            <button type="submit" class="followup-submit">Send</button>
          </form>
        </div>
      </div>
    `;

        const toggleBtn = item.querySelector(".followup-toggle");
        const panel = item.querySelector(".followup-panel");
        const threadEl = item.querySelector(".followup-thread");
        const errorEl = item.querySelector(".followup-error");
        const formEl = item.querySelector(".followup-form");
        const inputEl = item.querySelector(".followup-input");
        const sendBtn = item.querySelector(".followup-submit");

        toggleBtn.addEventListener("click", async () => {
            const isHidden = panel.classList.contains("hidden");
            panel.classList.toggle("hidden", !isHidden);
            toggleBtn.textContent = isHidden ? "Hide Follow-Up" : "Show Follow-Up";

            if (isHidden) {
                try {
                    await loadFollowupMessages(row.id, threadEl, errorEl);
                } catch (error) {
                    errorEl.textContent = "Could not load follow-up history.";
                    log(statusLog, `Follow-up history load failed for upload ${row.id}: ${error.message}`);
                }
            }
        });

        formEl.addEventListener("submit", async (event) => {
            event.preventDefault();
            const question = inputEl.value.trim();
            if (!question) {
                return;
            }

            setLoading(sendBtn, "Sending...", true);
            try {
                await submitFollowup(row.id, question, threadEl, errorEl);
                inputEl.value = "";
                log(statusLog, `Follow-up answered for upload ${row.id}.`);
            } catch (error) {
                errorEl.textContent = "Could not send follow-up. Please try again.";
                log(statusLog, `Follow-up failed for upload ${row.id}: ${error.message}`);
            } finally {
                setLoading(sendBtn, "", false);
            }
        });

        uploadsList.appendChild(item);
    }

    log(statusLog, `Loaded ${data.length} upload(s).`);
}

async function bootstrapDashboard() {
    const user = await validateSession();
    if (!user) {
        redirect("/login");
        return;
    }

    authStatus.textContent = `Logged in as ${user.email}`;
    authStatus.classList.add("ok");

    gate.classList.add("hidden");
    dashboardContent.classList.remove("hidden");

    try {
        await loadUploads();
    } catch (error) {
        showToast(`Could not load uploads: ${error.message}`, "error");
        log(statusLog, `Initial upload load failed: ${error.message}`);
    }
}

uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fileInput = document.getElementById("upload-file");
    const file = fileInput.files[0];

    if (!file) {
        showToast("Please select a file before upload.", "error");
        return;
    }

    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    setLoading(uploadBtn, isPdf ? "Processing PDF pages..." : "Uploading...", true);
    const formData = new FormData();
    formData.append("file", file);

    try {
        const result = await requestAuthJson("/uploads", {
            method: "POST",
            body: formData,
        });
        fileInput.value = "";
        const state = result.processing_state || "success";
        const note = result.processing_note || "";
        const message =
            state === "failure"
                ? `Upload complete, but extraction failed. ${note}`
                : state === "partial"
                    ? `Upload complete with limits applied. ${note}`
                    : "Upload complete and processed successfully.";
        showToast(message, stateToastKind(state));
        log(statusLog, `Upload finished with state=${state}. ${note}`.trim());
        await loadUploads();
    } catch (error) {
        if (error.status === 401) {
            clearToken();
            redirect("/login");
            return;
        }
        showToast(`Upload failed: ${error.message}`, "error");
        log(statusLog, `Upload failed: ${error.message}`);
    } finally {
        setLoading(uploadBtn, "", false);
    }
});

refreshBtn.addEventListener("click", async () => {
    setLoading(refreshBtn, "Refreshing...", true);
    try {
        await loadUploads();
        showToast("Uploads refreshed", "success");
    } catch (error) {
        showToast(`Refresh failed: ${error.message}`, "error");
        log(statusLog, `Refresh failed: ${error.message}`);
    } finally {
        setLoading(refreshBtn, "", false);
    }
});

logoutBtn.addEventListener("click", () => {
    clearToken();
    redirect("/login");
});

bootstrapDashboard();
