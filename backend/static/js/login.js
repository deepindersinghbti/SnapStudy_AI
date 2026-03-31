import {
    requestJson,
    setToken,
    setLoading,
    showToast,
    validateSession,
    redirect,
} from "/static/js/utils.js";

const loginForm = document.getElementById("login-form");
const loginBtn = document.getElementById("login-btn");

async function bootstrap() {
    const user = await validateSession();
    if (user) {
        redirect("/dashboard");
    }
}

loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;

    setLoading(loginBtn, "Signing in...", true);
    try {
        const data = await requestJson("/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        });

        setToken(data.access_token);
        showToast("Login successful", "success");
        redirect("/dashboard");
    } catch (error) {
        showToast(`Login failed: ${error.message}`, "error");
    } finally {
        setLoading(loginBtn, "", false);
    }
});

bootstrap();
