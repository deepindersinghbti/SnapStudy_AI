const registerForm = document.getElementById("register-form");
const loginForm = document.getElementById("login-form");
const uploadForm = document.getElementById("upload-form");
const uploadBtn = document.getElementById("upload-btn");
const refreshBtn = document.getElementById("refresh-btn");
const logoutBtn = document.getElementById("logout-btn");
const uploadsList = document.getElementById("uploads-list");
const statusLog = document.getElementById("status-log");
const authStatus = document.getElementById("auth-status");
const showLoginBtn = document.getElementById("show-login");
const showRegisterBtn = document.getElementById("show-register");
const loginPanel = document.getElementById("login-panel");
const registerPanel = document.getElementById("register-panel");
const authMessage = document.getElementById("auth-message");

const TOKEN_KEY = "snapstudy_token";

/**
 * Apply inline markdown formatting (bold, italic) to text.
 * Assumes text has already been HTML-escaped.
 */
function applyInlineFormatting(text) {
  // Convert **bold** to <strong>bold</strong>
  let result = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Convert *italic* to <em>italic</em>
  result = result.replace(/\*(.+?)\*/g, "<em>$1</em>");

  return result;
}

/**
 * Convert markdown table to HTML table.
 * Assumes lines are already escaped and are table rows (start with |).
 */
function convertMarkdownTable(tableLines) {
  if (tableLines.length < 2) return null;

  // First line is headers
  const headerCells = tableLines[0]
    .split("|")
    .map(cell => cell.trim())
    .filter(cell => cell.length > 0);

  // Skip separator line (line 1)
  // Data starts at line 2
  const dataRows = tableLines.slice(2).map(line =>
    line
      .split("|")
      .map(cell => cell.trim())
      .filter(cell => cell.length > 0)
  );

  if (headerCells.length === 0) return null;

  // Build HTML table
  let tableHtml = '<table class="markdown-table"><thead><tr>';
  headerCells.forEach(header => {
    tableHtml += `<th>${applyInlineFormatting(header)}</th>`;
  });
  tableHtml += '</tr></thead><tbody>';

  dataRows.forEach(rowCells => {
    tableHtml += '<tr>';
    rowCells.forEach(cell => {
      tableHtml += `<td>${applyInlineFormatting(cell)}</td>`;
    });
    tableHtml += '</tr>';
  });

  tableHtml += '</tbody></table>';
  return tableHtml;
}

/**
 * Convert markdown formatting to HTML while safely escaping HTML entities.
 * Supports: **bold**, *italic*, tables (|...|), newlines → <br>
 */
function markdownToHtml(text) {
  if (!text) return "";

  // 1. Escape HTML entities to prevent XSS
  let html = String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  // 2. Split into lines and process tables
  const lines = html.split("\n");
  const result = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Check if this is a table line (starts with |, ends with |)
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      // Collect table lines
      const tableLines = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }

      // Try to convert to table (needs at least header + separator + data)
      const tableHtml = convertMarkdownTable(tableLines);
      if (tableHtml) {
        result.push(tableHtml);
      } else {
        // Not a valid table, treat as regular lines
        tableLines.forEach(tl => result.push(applyInlineFormatting(tl)));
      }
    } else {
      // Regular line - apply inline formatting and convert newlines
      result.push(applyInlineFormatting(line));
      i++;
    }
  }

  // 3. Join with <br> for newlines
  html = result.join("<br>");

  return html;
}

function log(message) {
  const line = `[${new Date().toLocaleTimeString()}] ${message}`;
  statusLog.textContent = `${line}\n${statusLog.textContent}`.trim();
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function setLoading(button, loadingText, isLoading) {
  if (!button.dataset.defaultText) {
    button.dataset.defaultText = button.textContent;
  }
  button.disabled = isLoading;
  button.textContent = isLoading ? loadingText : button.dataset.defaultText;
}

function showAuthMessage(message) {
  authMessage.textContent = message;
  authMessage.classList.add("show");
}

function clearAuthMessage() {
  authMessage.textContent = "";
  authMessage.classList.remove("show");
}

function setAuthMode(mode) {
  const isLogin = mode === "login";
  loginPanel.classList.toggle("hidden", !isLogin);
  registerPanel.classList.toggle("hidden", isLogin);
  showLoginBtn.classList.toggle("active", isLogin);
  showRegisterBtn.classList.toggle("active", !isLogin);
  showLoginBtn.setAttribute("aria-selected", String(isLogin));
  showRegisterBtn.setAttribute("aria-selected", String(!isLogin));
}

function updateAuthUi() {
  const hasToken = !!getToken();
  authStatus.textContent = hasToken ? "Logged in" : "Not logged in";
  authStatus.classList.toggle("ok", hasToken);
  uploadBtn.disabled = !hasToken;
  refreshBtn.disabled = !hasToken;
  logoutBtn.disabled = !hasToken;
}

async function requestJson(url, options = {}) {
  const res = await fetch(url, options);
  const contentType = res.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof body === "string" ? body : body.detail || JSON.stringify(body);
    throw new Error(`${res.status} ${detail}`);
  }
  return body;
}

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("register-email").value.trim();
  const password = document.getElementById("register-password").value;

  const submitBtn = registerForm.querySelector("button[type='submit']");
  setLoading(submitBtn, "Creating...", true);
  try {
    await requestJson("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    registerForm.reset();
    showAuthMessage("Registration successful! You can now log in.");
    setAuthMode("login");
    log(`Registered user: ${email}`);
  } catch (error) {
    clearAuthMessage();
    log(`Register failed: ${error.message}`);
  } finally {
    setLoading(submitBtn, "", false);
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;

  const submitBtn = loginForm.querySelector("button[type='submit']");
  setLoading(submitBtn, "Signing in...", true);
  try {
    const data = await requestJson("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    setToken(data.access_token);
    updateAuthUi();
    loginForm.reset();
    clearAuthMessage();
    log("Login successful. Token saved in browser.");
    await loadUploads();
  } catch (error) {
    log(`Login failed: ${error.message}`);
  } finally {
    setLoading(submitBtn, "", false);
  }
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("upload-file");
  const file = fileInput.files[0];
  if (!file) {
    log("Please pick a file before uploading.");
    return;
  }

  setLoading(uploadBtn, "Uploading...", true);
  const formData = new FormData();
  formData.append("file", file);

  try {
    const token = getToken();
    await requestJson("/uploads", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    fileInput.value = "";
    log("Upload successful. Refreshing upload list...");
    await loadUploads();
  } catch (error) {
    log(`Upload failed: ${error.message}`);
  } finally {
    setLoading(uploadBtn, "", false);
  }
});

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  try {
    await loadUploads();
  } finally {
    updateAuthUi();
  }
});

logoutBtn.addEventListener("click", () => {
  clearToken();
  uploadsList.innerHTML = "";
  updateAuthUi();
  log("Logged out and token removed.");
});

showLoginBtn.addEventListener("click", () => {
  clearAuthMessage();
  setAuthMode("login");
});

showRegisterBtn.addEventListener("click", () => {
  clearAuthMessage();
  setAuthMode("register");
});

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
  const token = getToken();
  if (!token) {
    return;
  }

  errorEl.textContent = "";
  const data = await requestJson(`/uploads/${uploadId}/followups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  renderFollowupMessages(threadEl, data.messages || []);
}

async function submitFollowup(uploadId, question, threadEl, errorEl) {
  const token = getToken();
  if (!token) {
    throw new Error("Not logged in");
  }

  const data = await requestJson(`/uploads/${uploadId}/followups`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });

  const emptyEl = threadEl.querySelector(".followup-empty");
  if (emptyEl) {
    emptyEl.remove();
  }
  threadEl.appendChild(
    createFollowupMessageNode({
      question: data.question,
      response: data.response,
    }),
  );
  threadEl.scrollTop = threadEl.scrollHeight;
  errorEl.textContent = "";
}

async function loadUploads() {
  const token = getToken();
  if (!token) {
    return;
  }

  const data = await requestJson("/uploads", {
    headers: { Authorization: `Bearer ${token}` },
  });

  uploadsList.innerHTML = "";

  if (!Array.isArray(data) || data.length === 0) {
    uploadsList.innerHTML = "<p>No uploads yet.</p>";
    log("No uploads found for this account.");
    return;
  }

  for (const row of data) {
    const item = document.createElement("article");
    item.className = "upload-item";
    item.innerHTML = `
      <p class="upload-meta"><strong>ID:</strong> ${row.id} | <strong>Type:</strong> ${row.file_type}</p>
      <p class="upload-block"><strong>Extracted Text</strong><br>${markdownToHtml(row.extracted_text || "(empty)")}</p>
      <p class="upload-block"><strong>Explanation</strong><br>${markdownToHtml(row.explanation || "(empty)")}</p>
      <div class="followup-wrap">
        <button type="button" class="secondary followup-toggle">Ask Follow-Up</button>
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
      toggleBtn.textContent = isHidden ? "Hide Follow-Up" : "Ask Follow-Up";

      if (isHidden) {
        try {
          await loadFollowupMessages(row.id, threadEl, errorEl);
        } catch (error) {
          errorEl.textContent = "Could not load follow-up history.";
          log(`Follow-up history load failed for upload ${row.id}: ${error.message}`);
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
        log(`Follow-up answered for upload ${row.id}.`);
      } catch (error) {
        errorEl.textContent = "Could not send follow-up. Please try again.";
        log(`Follow-up failed for upload ${row.id}: ${error.message}`);
      } finally {
        setLoading(sendBtn, "", false);
      }
    });

    uploadsList.appendChild(item);
  }

  log(`Loaded ${data.length} upload(s).`);
}

updateAuthUi();
setAuthMode("login");
if (getToken()) {
  loadUploads().catch((err) => log(`Initial load failed: ${err.message}`));
}
