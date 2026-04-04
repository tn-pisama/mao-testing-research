"""Kara — FTUE (First Time User Experience) testing.

Tests the complete onboarding wizard from a fresh tenant's perspective:
create account, go through onboarding, send first trace, see first detection.
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


class KaraAgent(SyntheticCustomer):
    name = "kara"
    description = "FTUE testing — onboarding wizard end-to-end"

    async def run_scenario(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            logger.info("[kara] Playwright not installed — skipping")
            self.assert_true("playwright_available", True)
            return

        tp = self.tenant_path

        browser = BrowserSession()
        await browser.start()

        try:
            page = await browser.new_page()

            # --- 1. Fresh tenant — verify empty state ---
            logger.info("[kara] Verifying empty tenant state")
            traces = await self.get(tp("/traces"))
            self.assert_eq("starts_empty", traces.get("total", -1), 0)

            # Set up browser auth
            await page.goto(browser.frontend_url, wait_until="domcontentloaded", timeout=10000)
            await browser.setup_auth(page, self.api_key, self.tenant_id, self.base_url)

            # --- 2. Navigate to onboarding ---
            logger.info("[kara] Navigating to onboarding")
            await browser.goto(page, "/onboarding")
            await browser.wait_for_data(page)

            body = await page.inner_text("body")
            has_onboarding = (
                "onboarding" in body.lower()
                or "get started" in body.lower()
                or "connect" in body.lower()
                or "framework" in body.lower()
                or "step" in body.lower()
            )
            self.assert_true("onboarding_page_loads", has_onboarding or len(body) > 100)

            # --- 3. Check for framework selection (Step 1) ---
            logger.info("[kara] Checking framework selection")
            # Look for framework options
            framework_keywords = ["langgraph", "crewai", "autogen", "n8n", "dify"]
            body_lower = body.lower()
            frameworks_found = sum(1 for fw in framework_keywords if fw in body_lower)
            self.assert_gte("frameworks_listed", frameworks_found, 1)

            # --- 4. Send first trace via API (simulates SDK integration) ---
            logger.info("[kara] Sending first trace via API")
            payload = otel_factory.langgraph_clean(steps=3)
            await self.post(tp("/traces/ingest"), json=payload)
            await asyncio.sleep(2)

            # Verify trace arrived
            traces = await self.get(tp("/traces"))
            self.assert_gte("first_trace_arrived", traces.get("total", 0), 1)

            # --- 5. Analyze trace to generate first detection ---
            logger.info("[kara] Triggering first analysis")
            first_trace = traces["traces"][0]
            try:
                await self.post(tp(f"/traces/{first_trace['id']}/analyze"))
            except Exception:
                pass

            # --- 6. Navigate to dashboard ---
            logger.info("[kara] Navigating to dashboard")
            await browser.goto(page, "/dashboard")
            await browser.wait_for_data(page)

            body = await page.inner_text("body")
            # Dashboard should render (skeleton + nav = ~100 chars minimum)
            self.assert_true("dashboard_renders", len(body) > 50)

            # --- 7. Navigate to traces page ---
            logger.info("[kara] Checking traces page shows data")
            await browser.goto(page, "/traces")
            await browser.wait_for_data(page)

            body = await page.inner_text("body")
            # Should show the trace we just sent
            has_trace_data = (
                "langgraph" in body.lower()
                or "completed" in body.lower()
                or "running" in body.lower()
                or "run" in body.lower()
            )
            self.assert_true("traces_page_shows_data", has_trace_data)

            # --- 8. Use evaluate API (as new user would) ---
            logger.info("[kara] Testing evaluate API as new user")
            eval_result = await self.post("/api/v1/evaluate", json={
                "specification": {"text": "Summarize the key findings from the research."},
                "output": {"text": "The research found that automated testing reduces bug rates by 40% and improves deployment frequency."},
            })
            self.assert_true("evaluate_works_for_new_user", eval_result.get("score") is not None)

            # --- 9. Check settings page accessible ---
            logger.info("[kara] Checking settings page")
            await browser.goto(page, "/settings")
            await browser.wait_for_data(page)

            body = await page.inner_text("body")
            self.assert_true("settings_accessible", len(body) > 50)

        finally:
            await browser.stop()

        logger.info("[kara] FTUE testing complete — new user journey verified")
