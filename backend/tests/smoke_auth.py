import argparse
import asyncio
from dataclasses import dataclass

from playwright.async_api import BrowserContext, Page, async_playwright


@dataclass
class SmokeResult:
    name: str
    passed: bool
    details: str = ""


async def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def stub_auth_success(context: BrowserContext) -> None:
    async def handler(route):
        await route.fulfill(
            status=200,
            content_type="application/json",
            body='{"id": 1, "email": "smoke@example.com", "created_at": "2026-01-01T00:00:00Z"}',
        )

    await context.route("**/auth/me", handler)


async def stub_uploads_empty(context: BrowserContext) -> None:
    async def handler(route):
        await route.fulfill(status=200, content_type="application/json", body="[]")

    await context.route("**/uploads", handler)


async def test_dashboard_redirects_when_unauthenticated(base_url: str) -> SmokeResult:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(f"{base_url}/dashboard", wait_until="domcontentloaded")
        await page.wait_for_url(f"{base_url}/login", timeout=5000)
        await expect(page.url.endswith("/login"), f"Expected /login, got {page.url}")

        await browser.close()
        return SmokeResult("dashboard redirect unauthenticated", True)


async def test_auth_pages_redirect_when_authenticated(base_url: str) -> list[SmokeResult]:
    results: list[SmokeResult] = []

    for path in ("/login", "/register"):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            await context.add_init_script(
                "window.localStorage.setItem('snapstudy_token', 'smoke-token');"
            )
            await stub_auth_success(context)
            await stub_uploads_empty(context)

            page = await context.new_page()
            await page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
            await page.wait_for_url(f"{base_url}/dashboard", timeout=5000)
            await expect(page.url.endswith("/dashboard"), f"{path} should redirect to /dashboard, got {page.url}")

            await browser.close()
            results.append(SmokeResult(
                f"{path} redirects authenticated user", True))

    return results


async def test_dashboard_no_flash_before_auth(base_url: str) -> SmokeResult:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_init_script(
            "window.localStorage.setItem('snapstudy_token', 'smoke-token');"
        )

        auth_release = asyncio.Event()

        async def auth_handler(route):
            # Hold auth response briefly to verify that dashboard content stays hidden.
            await auth_release.wait()
            await route.fulfill(
                status=200,
                content_type="application/json",
                body='{"id": 1, "email": "smoke@example.com", "created_at": "2026-01-01T00:00:00Z"}',
            )

        await context.route("**/auth/me", auth_handler)
        await stub_uploads_empty(context)

        page = await context.new_page()
        await page.goto(f"{base_url}/dashboard", wait_until="domcontentloaded")

        is_hidden_before = await page.evaluate(
            "() => document.getElementById('dashboard-content').classList.contains('hidden')"
        )
        gate_visible_before = await page.evaluate(
            "() => !document.getElementById('dashboard-gate').classList.contains('hidden')"
        )

        await expect(is_hidden_before, "dashboard-content should be hidden before auth validation resolves")
        await expect(gate_visible_before, "dashboard gate should be visible before auth validation resolves")

        auth_release.set()
        await page.wait_for_selector("#dashboard-content:not(.hidden)", timeout=5000)

        await browser.close()
        return SmokeResult("dashboard no-flash before auth", True)


async def run(base_url: str) -> int:
    checks: list[SmokeResult] = []

    try:
        checks.append(await test_dashboard_redirects_when_unauthenticated(base_url))
    except Exception as exc:
        checks.append(SmokeResult(
            "dashboard redirect unauthenticated", False, str(exc)))

    try:
        checks.extend(await test_auth_pages_redirect_when_authenticated(base_url))
    except Exception as exc:
        checks.append(SmokeResult(
            "auth page redirect authenticated", False, str(exc)))

    try:
        checks.append(await test_dashboard_no_flash_before_auth(base_url))
    except Exception as exc:
        checks.append(SmokeResult(
            "dashboard no-flash before auth", False, str(exc)))

    failed = [check for check in checks if not check.passed]

    print("\nSmoke test results")
    print("==================")
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        suffix = f" :: {check.details}" if check.details else ""
        print(f"[{status}] {check.name}{suffix}")

    if failed:
        print(f"\n{len(failed)} check(s) failed.")
        return 1

    print("\nAll checks passed.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lightweight browser smoke checks for auth redirects and dashboard auth-gate behavior."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL where SnapStudy backend is running.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exit_code = asyncio.run(run(args.base_url.rstrip("/")))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
