from __future__ import annotations

import asyncio
import base64
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class BrowserPage:
    page: object
    context: object




def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP(S) URLs are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are not allowed.")
    hostname = parsed.hostname.strip().lower()
    if hostname in {"localhost", "localhost.localdomain", "metadata.google.internal", "metadata.google.internal."} or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValueError("Private or local network targets are blocked.")
    try:
        direct = ipaddress.ip_address(hostname)
        addresses = [direct]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)]
        except OSError as exc:
            raise ValueError("The target host could not be resolved.") from exc
    for address in addresses:
        if address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified:
            raise ValueError("Private or local network targets are blocked.")

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
        _assert_public_url(url)
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
