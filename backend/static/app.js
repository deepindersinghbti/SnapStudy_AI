const registerForm = document.getElementById("register-form");
const loginForm = document.getElementById("login-form");
const uploadForm = document.getElementById("upload-form");
const uploadBtn = document.getElementById("upload-btn");
const refreshBtn = document.getElementById("refresh-btn");
const logoutBtn = document.getElementById("logout-btn");
const uploadsList = document.getElementById("uploads-list");
const statusLog = document.getElementById("status-log");
const authStatus = document.getElementById("auth-status");

const TOKEN_KEY = "snapstudy_token";

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
    log(`Registered user: ${email}`);
  } catch (error) {
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
      <p class="upload-block"><strong>Extracted Text</strong>\n${row.extracted_text || "(empty)"}</p>
      <p class="upload-block"><strong>Explanation</strong>\n${row.explanation || "(empty)"}</p>
    `;
    uploadsList.appendChild(item);
  }

  log(`Loaded ${data.length} upload(s).`);
}

updateAuthUi();
if (getToken()) {
  loadUploads().catch((err) => log(`Initial load failed: ${err.message}`));
}
