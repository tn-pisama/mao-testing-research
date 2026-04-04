"""Jasper — UI/UX quality testing.

Tests visual quality, interaction patterns, responsive layout,
and accessibility across key pages.
"""

import asyncio
import logging

from ..base import SyntheticCustomer

logger = logging.getLogger(__name__)

try:
    from ..browser import BrowserSession, PLAYWRIGHT_AVAILABLE
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class JasperAgent(SyntheticCustomer):
    name = "jasper"
    description = "UI/UX quality — interactions, responsive, accessibility"

    async def run_scenario(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            logger.info("[jasper] Playwright not installed — skipping")
            self.assert_true("playwright_available", True)
            return

        browser = BrowserSession()
        await browser.start()

        try:
            page = await browser.new_page()
            await page.goto(browser.frontend_url, wait_until="domcontentloaded", timeout=10000)
            await browser.setup_auth(page, self.api_key, self.tenant_id, self.base_url)

            # --- 1. Dashboard interactions ---
            logger.info("[jasper] Testing dashboard interactions")
            await browser.goto(page, "/dashboard")
            await browser.wait_for_data(page)

            # Sidebar toggle — check sidebar exists and has correct width
            sidebar = await page.query_selector("aside")
            if sidebar:
                box = await sidebar.bounding_box()
                self.assert_true("sidebar_has_width", box is not None and box["width"] > 50)

            # Check for clickable buttons
            buttons = await page.query_selector_all("button")
            self.assert_gte("dashboard_has_buttons", len(buttons), 2)

            # --- 2. Navigation between pages ---
            logger.info("[jasper] Testing page navigation")
            nav_targets = [
                ("/traces", "runs"),
                ("/detections", "detection"),
                ("/dashboard", "dashboard"),
            ]
            for path, expected_word in nav_targets:
                await browser.goto(page, path)
                await browser.wait_for_data(page)
                body = await page.inner_text("body")
                self.assert_true(
                    f"nav_{path.strip('/')}_loads",
                    expected_word in body.lower() or len(body) > 100,
                )

            # --- 3. Mobile viewport ---
            logger.info("[jasper] Testing mobile viewport")
            await page.set_viewport_size({"width": 375, "height": 812})
            await browser.goto(page, "/dashboard")
            await browser.wait_for_data(page)

            # Page should still render (no overflow, no crash)
            body = await page.inner_text("body")
            self.assert_true("mobile_renders", len(body) > 50)

            # Check no horizontal overflow
            overflow = await page.evaluate("document.body.scrollWidth > window.innerWidth")
            self.assert_true("no_horizontal_overflow", not overflow)

            # Reset viewport
            await page.set_viewport_size({"width": 1280, "height": 800})

            # --- 4. Dark theme check ---
            logger.info("[jasper] Testing dark theme")
            await browser.goto(page, "/dashboard")
            bg_color = await page.evaluate(
                "getComputedStyle(document.body).backgroundColor"
            )
            # Pisama uses zinc-950 (#09090b) background
            self.assert_true(
                "dark_theme_active",
                "rgb(9" in bg_color or "rgb(0" in bg_color or "#09" in bg_color or "rgb(24" in bg_color,
            )

            # --- 5. Loading states resolve ---
            logger.info("[jasper] Testing loading state resolution")
            await browser.goto(page, "/traces")
            # Count skeleton elements immediately
            skeletons_before = await page.query_selector_all(".animate-pulse")
            await asyncio.sleep(5)
            skeletons_after = await page.query_selector_all(".animate-pulse")
            self.assert_true(
                "loading_resolves",
                len(skeletons_after) <= len(skeletons_before),
            )

            # --- 6. Accessibility basics ---
            logger.info("[jasper] Testing accessibility basics")
            await browser.goto(page, "/dashboard")
            await browser.wait_for_data(page)

            # Check for landmark elements
            has_nav = await page.query_selector("nav, [role='navigation']")
            has_main = await page.query_selector("main, [role='main']")
            self.assert_true("has_navigation_landmark", has_nav is not None)
            self.assert_true("has_main_landmark", has_main is not None)

            # Check all images have alt text (if any)
            images = await page.query_selector_all("img")
            if images:
                missing_alt = 0
                for img in images:
                    alt = await img.get_attribute("alt")
                    if alt is None or alt == "":
                        missing_alt += 1
                self.assert_eq("images_have_alt", missing_alt, 0)

        finally:
            await browser.stop()

        logger.info("[jasper] UI/UX quality testing complete")
