import {
    requestJson,
    setLoading,
    showToast,
    validateSession,
    redirect,
} from "/static/js/utils.js";

const registerForm = document.getElementById("register-form");
const registerBtn = document.getElementById("register-btn");

async function bootstrap() {
    const user = await validateSession();
    if (user) {
        redirect("/dashboard");
    }
}

registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("register-email").value.trim();
    const password = document.getElementById("register-password").value;
    const confirmPassword = document.getElementById("register-confirm-password").value;

    if (password !== confirmPassword) {
        showToast("Passwords do not match", "error");
        return;
    }

    setLoading(registerBtn, "Creating...", true);
    try {
        await requestJson("/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        });

        showToast("Registration successful. Please log in.", "success");
        redirect("/login");
    } catch (error) {
        showToast(`Registration failed: ${error.message}`, "error");
    } finally {
        setLoading(registerBtn, "", false);
    }
});

bootstrap();
