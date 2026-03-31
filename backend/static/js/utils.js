const TOKEN_KEY = "snapstudy_token";

export function getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
}

export function withAuthHeaders(headers = {}) {
    const token = getToken();
    if (!token) {
        return headers;
    }
    return { ...headers, Authorization: `Bearer ${token}` };
}

export async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json")
        ? await response.json()
        : await response.text();

    if (!response.ok) {
        const detail = typeof body === "string" ? body : body.detail || JSON.stringify(body);
        const error = new Error(`${response.status} ${detail}`);
        error.status = response.status;
        throw error;
    }

    return body;
}

export async function requestAuthJson(url, options = {}) {
    const headers = withAuthHeaders(options.headers || {});
    return requestJson(url, { ...options, headers });
}

export function redirect(path) {
    window.location.href = path;
}

export async function validateSession() {
    const token = getToken();
    if (!token) {
        return null;
    }

    try {
        return await requestAuthJson("/auth/me");
    } catch {
        clearToken();
        return null;
    }
}

export function setLoading(button, loadingText, isLoading) {
    if (!button.dataset.defaultText) {
        button.dataset.defaultText = button.textContent;
    }
    button.disabled = isLoading;
    button.textContent = isLoading ? loadingText : button.dataset.defaultText;
}

export function log(statusLog, message) {
    if (!statusLog) {
        return;
    }
    const line = `[${new Date().toLocaleTimeString()}] ${message}`;
    statusLog.textContent = `${line}\n${statusLog.textContent}`.trim();
}

export function showToast(message, kind = "info") {
    const root = document.getElementById("toast-root");
    if (!root) {
        return;
    }

    const toast = document.createElement("div");
    toast.className = `toast ${kind}`;
    toast.textContent = message;
    root.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("show");
    }, 5);

    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 220);
    }, 2600);
}

export function formatTimestamp(value) {
    if (!value) {
        return "-";
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return String(value);
    }

    return parsed.toLocaleString();
}

export function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function applyInlineFormatting(text) {
    let result = text.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    result = result.replace(/\*(.+?)\*/g, "<em>$1</em>");
    return result;
}

function convertMarkdownTable(tableLines) {
    if (tableLines.length < 2) {
        return null;
    }

    const headerCells = tableLines[0]
        .split("|")
        .map((cell) => cell.trim())
        .filter((cell) => cell.length > 0);

    const dataRows = tableLines.slice(2).map((line) =>
        line
            .split("|")
            .map((cell) => cell.trim())
            .filter((cell) => cell.length > 0)
    );

    if (headerCells.length === 0) {
        return null;
    }

    let tableHtml = '<table class="markdown-table"><thead><tr>';
    headerCells.forEach((header) => {
        tableHtml += `<th>${applyInlineFormatting(header)}</th>`;
    });
    tableHtml += "</tr></thead><tbody>";

    dataRows.forEach((rowCells) => {
        tableHtml += "<tr>";
        rowCells.forEach((cell) => {
            tableHtml += `<td>${applyInlineFormatting(cell)}</td>`;
        });
        tableHtml += "</tr>";
    });

    tableHtml += "</tbody></table>";
    return tableHtml;
}

export function markdownToHtml(text) {
    if (!text) {
        return "";
    }

    const escaped = escapeHtml(text);
    const lines = escaped.split("\n");
    const result = [];
    let i = 0;

    while (i < lines.length) {
        const line = lines[i];

        if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
            const tableLines = [];
            while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
                tableLines.push(lines[i]);
                i += 1;
            }

            const tableHtml = convertMarkdownTable(tableLines);
            if (tableHtml) {
                result.push(tableHtml);
            } else {
                tableLines.forEach((entry) => result.push(applyInlineFormatting(entry)));
            }
        } else {
            result.push(applyInlineFormatting(line));
            i += 1;
        }
    }

    return result.join("<br>");
}
