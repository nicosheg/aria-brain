from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass


@dataclass
class BrowserPage:
    page: object
    context: object


class BrowserController:
    """Persistent per-user browser sessions for UI-level automation."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._playwright = None
        self._browser = None
        self._pages: dict[str, BrowserPage] = {}
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        if not self.enabled:
            raise RuntimeError("Browser control is disabled.")
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            raise RuntimeError("Playwright is not installed or browser dependencies are unavailable.") from exc
        async with self._lock:
            if self._browser is None:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage", "--no-sandbox"],
                )

    async def page_for(self, user_id: str):
        await self._ensure_browser()
        if user_id not in self._pages:
            context = await self._browser.new_context(viewport={"width": 1280, "height": 720}, user_agent="ARIA-Agent/1.0")
            page = await context.new_page()
            self._pages[user_id] = BrowserPage(page=page, context=context)
        return self._pages[user_id].page

    async def navigate(self, user_id: str, url: str) -> str:
        if not (url.startswith("https://") or url.startswith("http://")):
            raise ValueError("Only http(s) URLs are allowed.")
        page = await self.page_for(user_id)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return await self.snapshot(user_id)

    async def snapshot(self, user_id: str) -> str:
        page = await self.page_for(user_id)
        title = await page.title()
        text = await page.locator("body").inner_text(timeout=10000)
        text = " ".join(text.split())
        return f"title={title!r}\nurl={page.url}\npage_text={text[:12000]}"

    async def screenshot(self, user_id: str) -> str:
        page = await self.page_for(user_id)
        png = await page.screenshot(type="png")
        return base64.b64encode(png).decode("ascii")

    async def click(self, user_id: str, selector: str) -> str:
        page = await self.page_for(user_id)
        await page.locator(selector).first.click(timeout=15000)
        return await self.snapshot(user_id)

    async def fill(self, user_id: str, selector: str, value: str) -> str:
        page = await self.page_for(user_id)
        await page.locator(selector).first.fill(value, timeout=15000)
        return await self.snapshot(user_id)

    async def press(self, user_id: str, selector: str, key: str) -> str:
        page = await self.page_for(user_id)
        await page.locator(selector).first.press(key, timeout=15000)
        return await self.snapshot(user_id)

    async def submit(self, user_id: str, selector: str) -> str:
        page = await self.page_for(user_id)
        await page.locator(selector).first.evaluate("(el) => el.requestSubmit ? el.requestSubmit() : el.click()")
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        return await self.snapshot(user_id)

    async def close_user(self, user_id: str) -> None:
        current = self._pages.pop(user_id, None)
        if current:
            await current.context.close()

    async def close(self):
        for uid in list(self._pages):
            await self.close_user(uid)
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None
