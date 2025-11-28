"""
browser.py
Playwright-based headless browser helpers.
This module provides a small synchronous helper to:
 - launch a browser
 - fetch page content after JS
 - optionally click/select elements
 - take screenshots

Install Playwright and browsers before using:
    pip install playwright
    playwright install

For production, prefer async API and connection pooling.
"""
from playwright.sync_api import sync_playwright
from typing import Optional, Dict, Any

class BrowserController:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._browser:
                self._browser.close()
        finally:
            if self._playwright:
                self._playwright.stop()

    def fetch(self, url: str, wait_for: Optional[str] = None, timeout: int = 10000) -> Dict[str, Any]:
        with self._browser.new_page() as page:
            page.goto(url, wait_until="networkidle", timeout=timeout)

            # Give JS time to modify DOM (like filling <span class="origin">)
            page.wait_for_timeout(300)

            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=timeout)
                except Exception:
                    pass

            html = page.content()
            screenshot_path = "/tmp/page_screenshot.png"
            page.screenshot(path=screenshot_path, full_page=False)

            return {"html": html, "screenshot_path": screenshot_path}


    def click_and_extract(self, url: str, click_selector: str, wait_for: Optional[str] = None) -> Dict[str, Any]:
        with self._browser.new_page() as page:
            page.goto(url)
            page.click(click_selector)
            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=5000)
                except Exception:
                    pass
            return {"html": page.content()}
