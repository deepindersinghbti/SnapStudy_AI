# Browser Smoke Checks

This folder contains lightweight browser-level smoke checks for auth redirects and dashboard auth-gate behavior.

## What it verifies

- Unauthenticated visit to `/dashboard` redirects to `/login`
- Authenticated visits to `/login` and `/register` redirect to `/dashboard`
- Dashboard content stays hidden until auth validation resolves (no flash)

## One-time setup

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\tests\requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Run

Make sure the app is running (default expected URL is `http://127.0.0.1:8000`).

```powershell
.\.venv\Scripts\python.exe .\tests\smoke_auth.py
```

If your server runs on a different URL/port:

```powershell
.\.venv\Scripts\python.exe .\tests\smoke_auth.py --base-url http://127.0.0.1:8010
```
