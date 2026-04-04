"""Shared Playwright browser setup for frontend synth agents."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


FRONTEND_URL = "http://localhost:3000"


class BrowserSession:
    """Manages a headless Chromium browser for frontend testing."""

    def __init__(self, frontend_url: str = FRONTEND_URL):
        self.frontend_url = frontend_url
        self._pw: Any = None
        self._browser: Any = None

    async def start(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("playwright not installed — run: pip install playwright && playwright install chromium")
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)

    async def new_page(self) -> "Page":
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = await context.new_page()
        return page

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def setup_auth(self, page: "Page", api_key: str, tenant_id: str, backend_url: str) -> None:
        """Set up auth context in the browser via localStorage — bypasses NextAuth.

        Must be called after navigating to the frontend origin (so localStorage is accessible).
        """
        import httpx
        # Exchange API key for JWT
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{backend_url}/api/v1/auth/token", json={"api_key": api_key})
            token = resp.json()["access_token"]

        # Set localStorage values the frontend reads
        await page.evaluate(f"""() => {{
            localStorage.setItem('pisama_override_token', '{token}');
            localStorage.setItem('pisama_last_tenant', '{tenant_id}');
        }}""")

    async def goto(self, page: "Page", path: str, wait_for: str = "networkidle") -> None:
        """Navigate to a page and wait for it to settle."""
        url = f"{self.frontend_url}{path}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        try:
            await page.wait_for_load_state(wait_for, timeout=10000)
        except Exception:
            pass  # networkidle can timeout on long-polling pages

    async def wait_for_data(self, page: "Page", timeout_ms: int = 10000) -> None:
        """Wait for skeleton/loading states to resolve."""
        try:
            # Wait for loading indicators to disappear
            await page.wait_for_selector(".animate-pulse", state="hidden", timeout=timeout_ms)
        except Exception:
            pass  # No skeletons found = already loaded

    async def collect_console_errors(self, page: "Page") -> list[str]:
        """Collect JavaScript console errors from the page."""
        errors: list[str] = []

        def on_console(msg: Any) -> None:
            if msg.type == "error" and "react-devtools" not in msg.text.lower():
                errors.append(msg.text)

        page.on("console", on_console)
        return errors
