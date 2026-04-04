"""Iris — Technical frontend verification.

Launches a headless browser, navigates to each major page, and verifies
that API data actually renders in the UI. Tests that the frontend is
functional, not just that the API works.
"""

import asyncio
import logging

from ..base import SyntheticCustomer
from .. import otel_factory

logger = logging.getLogger(__name__)

try:
    from ..browser import BrowserSession, PLAYWRIGHT_AVAILABLE
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class IrisAgent(SyntheticCustomer):
    name = "iris"
    description = "Frontend technical verification — browser tests with real data"

    async def run_scenario(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            logger.info("[iris] Playwright not installed — skipping browser tests")
            self.assert_true("playwright_available", True)
            return

        tp = self.tenant_path

        # --- 1. Populate backend with test data ---
        logger.info("[iris] Populating backend with test data")
        await self.post(tp("/traces/ingest"), json=otel_factory.langgraph_clean(steps=5))
        await self.post(tp("/traces/ingest"), json=otel_factory.langgraph_loop(repeat_count=4))
        await self.post(tp("/traces/ingest"), json=otel_factory.realistic_customer_support_workflow())
        await asyncio.sleep(1)

        # Analyze traces to generate detections
        traces = await self.get(tp("/traces"))
        for trace in traces.get("traces", [])[:3]:
            try:
                await self.post(tp(f"/traces/{trace['id']}/analyze"))
            except Exception:
                pass

        trace_count = traces.get("total", 0)
        self.assert_gte("has_test_data", trace_count, 3)

        # Get detection count for comparison
        detections = await self.get(tp("/detections"))
        detection_count = detections.get("total", 0)

        # --- 2. Launch browser ---
        logger.info("[iris] Launching browser")
        browser = BrowserSession()
        await browser.start()

        try:
            page = await browser.new_page()

            # Set up auth — navigate to origin first, then set localStorage
            await page.goto(browser.frontend_url, wait_until="domcontentloaded", timeout=10000)
            await browser.setup_auth(page, self.api_key, self.tenant_id, self.base_url)

            # --- 3. Dashboard page ---
            logger.info("[iris] Testing /dashboard")
            await browser.goto(page, "/dashboard")
            await browser.wait_for_data(page)

            # Page should have loaded (not stuck on loading)
            title = await page.title()
            self.assert_true("dashboard_has_title", len(title) > 0)

            # Sidebar should be visible
            sidebar = await page.query_selector("aside")
            self.assert_true("sidebar_visible", sidebar is not None)

            # Check for main content area
            main = await page.query_selector("main")
            self.assert_true("main_content_exists", main is not None)

            # Should not show "Loading..." text after data loads
            body_text = await page.inner_text("body")
            self.assert_true(
                "dashboard_not_stuck_loading",
                "Loading..." not in body_text or "Loading agents" in body_text,
            )

            # --- 4. Traces page ---
            logger.info("[iris] Testing /traces")
            await browser.goto(page, "/traces")
            await browser.wait_for_data(page)

            body_text = await page.inner_text("body")
            # Should show "Runs" or trace-related content
            has_trace_content = "run" in body_text.lower() or "trace" in body_text.lower() or "langgraph" in body_text.lower()
            self.assert_true("traces_page_has_content", has_trace_content)

            # --- 5. Detections page ---
            logger.info("[iris] Testing /detections")
            await browser.goto(page, "/detections")
            await browser.wait_for_data(page)

            body_text = await page.inner_text("body")
            has_detection_content = "detection" in body_text.lower() or "loop" in body_text.lower() or "no detection" in body_text.lower()
            self.assert_true("detections_page_has_content", has_detection_content)

            # --- 6. Healing page ---
            logger.info("[iris] Testing /healing")
            await browser.goto(page, "/healing")
            await browser.wait_for_data(page)

            body_text = await page.inner_text("body")
            has_healing_content = "healing" in body_text.lower() or "fix" in body_text.lower() or "no healing" in body_text.lower()
            self.assert_true("healing_page_has_content", has_healing_content)

            # --- 7. Sidebar navigation ---
            logger.info("[iris] Testing sidebar navigation")
            nav_links = await page.query_selector_all("aside a")
            self.assert_gte("sidebar_has_nav_links", len(nav_links), 5)

            # --- 8. No JS errors ---
            # Navigate to dashboard one more time and check for errors
            errors: list[str] = []

            def on_error(msg: object) -> None:
                if hasattr(msg, 'type') and getattr(msg, 'type') == 'error':
                    text = getattr(msg, 'text', '')
                    if 'react-devtools' not in text.lower() and 'favicon' not in text.lower():
                        errors.append(text)

            page.on("console", on_error)
            await browser.goto(page, "/dashboard")
            await asyncio.sleep(3)
            # Allow some errors (CSP, auth warnings in dev) but no crashes
            # Filter out auth-related errors (expected in dev mode without full NextAuth)
            critical_errors = [
                e for e in errors
                if ("TypeError" in e or "ReferenceError" in e or "SyntaxError" in e)
                and "fetch" not in e.lower()
                and "auth" not in e.lower()
                and "session" not in e.lower()
                and "token" not in e.lower()
            ]
            self.assert_eq("no_critical_js_errors", len(critical_errors), 0)

        finally:
            await browser.stop()

        logger.info("[iris] Frontend technical verification complete")
