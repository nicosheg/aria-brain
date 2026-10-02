from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from pathlib import Path

from .security import assert_public_http_url


@dataclass
class BrowserPage:
    page: object
    context: object


class BrowserController:
    """Per-user, isolated Playwright sessions with inspectable UI element references."""

    def __init__(self, enabled: bool = True, max_sessions: int = 50):
        self.enabled = enabled
        self.max_sessions = max_sessions
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
            if len(self._pages) >= self.max_sessions:
                oldest_uid = next(iter(self._pages))
                await self.close_user(oldest_uid)
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="ARIA-Agent/1.0",
            )
            page = await context.new_page()
            self._pages[user_id] = BrowserPage(page=page, context=context)
        return self._pages[user_id].page

    async def navigate(self, user_id: str, url: str) -> str:
        safe_url = assert_public_http_url(url)
        page = await self.page_for(user_id)
        await page.goto(safe_url, wait_until="domcontentloaded", timeout=30000)
        assert_public_http_url(page.url)
        return await self.snapshot(user_id)

    async def _elements(self, user_id: str) -> list[dict]:
        page = await self.page_for(user_id)
        return await page.evaluate(
            """() => {
              const selector = [
                'a[href]', 'button', 'input', 'textarea', 'select',
                '[role="button"]', '[role="link"]', '[contenteditable="true"]'
              ].join(',');
              const clean = (value) => (value || '').replace(/\s+/g, ' ').trim().slice(0, 160);
              const elements = Array.from(document.querySelectorAll(selector))
                .filter((el) => {
                  const style = getComputedStyle(el);
                  const rect = el.getBoundingClientRect();
                  return style.visibility !== 'hidden' &&
                    style.display !== 'none' &&
                    rect.width > 0 && rect.height > 0;
                })
                .slice(0, 120);
              return elements.map((el, index) => {
                const ref = 'aria-' + (index + 1);
                el.setAttribute('data-aria-ref', ref);
                const role = el.getAttribute('role') || el.tagName.toLowerCase();
                return {
                  ref,
                  tag: el.tagName.toLowerCase(),
                  role,
                  type: el.getAttribute('type') || '',
                  name: el.getAttribute('name') || '',
                  aria_label: el.getAttribute('aria-label') || '',
                  placeholder: el.getAttribute('placeholder') || '',
                  text: clean(el.innerText || el.value || el.textContent),
                  href: el.getAttribute('href') || ''
                };
              });
            }"""
        )

    async def inspect(self, user_id: str) -> str:
        page = await self.page_for(user_id)
        title = await page.title()
        text = await page.locator("body").inner_text(timeout=10000)
        text = " ".join(text.split())
        elements = await self._elements(user_id)
        return json.dumps(
            {
                "title": title,
                "url": page.url,
                "page_text": text[:12000],
                "interactive_elements": elements,
            },
            ensure_ascii=False,
        )

    async def snapshot(self, user_id: str) -> str:
        return await self.inspect(user_id)

    async def screenshot(self, user_id: str) -> str:
        page = await self.page_for(user_id)
        data = await page.screenshot(type="png")
        return base64.b64encode(data).decode("ascii")

    async def element_info(self, user_id: str, ref: str) -> dict:
        await self._elements(user_id)
        page = await self.page_for(user_id)
        locator = page.locator(f'[data-aria-ref="{ref}"]').first
        if await locator.count() == 0:
            raise ValueError("The browser element reference is stale. Inspect the page again.")
        return await locator.evaluate(
            """el => ({
              ref: el.getAttribute('data-aria-ref'),
              tag: el.tagName.toLowerCase(),
              role: el.getAttribute('role') || el.tagName.toLowerCase(),
              type: el.getAttribute('type') || '',
              text: (el.innerText || el.value || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160),
              aria_label: el.getAttribute('aria-label') || '',
              href: el.getAttribute('href') || ''
            })"""
        )

    async def ref_needs_approval(self, user_id: str, ref: str) -> bool:
        info = await self.element_info(user_id, ref)
        blob = " ".join(
            str(info.get(k, "")).lower()
            for k in ("role", "type", "text", "aria_label", "href")
        )
        risky = (
            "submit", "delete", "remove", "pay", "purchase", "checkout", "send",
            "publish", "confirm", "save", "invite", "follow", "apply", "transfer",
            "withdraw", "buy", "post", "cancel", "password", "secret", "token",
            "otp", "one-time", "credit card", "debit card", "cvv", "bank",
            "login", "log in", "sign in",
        )
        return any(word in blob for word in risky)

    async def click(self, user_id: str, selector: str) -> str:
        page = await self.page_for(user_id)
        await page.locator(selector).first.click(timeout=15000)
        return await self.snapshot(user_id)

    async def click_ref(self, user_id: str, ref: str) -> str:
        await self._elements(user_id)
        page = await self.page_for(user_id)
        locator = page.locator(f'[data-aria-ref="{ref}"]').first
        if await locator.count() == 0:
            raise ValueError("The browser element reference is stale. Inspect the page again.")
        await locator.click(timeout=15000)
        return await self.snapshot(user_id)

    async def fill(self, user_id: str, selector: str, value: str) -> str:
        page = await self.page_for(user_id)
        await page.locator(selector).first.fill(value, timeout=15000)
        return await self.snapshot(user_id)

    async def fill_ref(self, user_id: str, ref: str, value: str) -> str:
        await self._elements(user_id)
        page = await self.page_for(user_id)
        locator = page.locator(f'[data-aria-ref="{ref}"]').first
        if await locator.count() == 0:
            raise ValueError("The browser element reference is stale. Inspect the page again.")
        await locator.fill(value, timeout=15000)
        return await self.snapshot(user_id)

    async def select_ref(self, user_id: str, ref: str, value: str) -> str:
        await self._elements(user_id)
        page = await self.page_for(user_id)
        locator = page.locator(f'[data-aria-ref="{ref}"]').first
        if await locator.count() == 0:
            raise ValueError("The browser element reference is stale. Inspect the page again.")
        await locator.select_option(value=value, timeout=15000)
        return await self.snapshot(user_id)

    async def press(self, user_id: str, selector: str, key: str) -> str:
        page = await self.page_for(user_id)
        await page.locator(selector).first.press(key, timeout=15000)
        return await self.snapshot(user_id)

    async def submit(self, user_id: str, selector: str) -> str:
        page = await self.page_for(user_id)
        await page.locator(selector).first.evaluate(
            "(el) => el.requestSubmit ? el.requestSubmit() : el.click()"
        )
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        return await self.snapshot(user_id)

    async def upload_ref(self, user_id: str, ref: str, file_path: str) -> str:
        await self._elements(user_id)
        page = await self.page_for(user_id)
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError("Upload file not found.")
        locator = page.locator(f'[data-aria-ref="{ref}"]').first
        if await locator.count() == 0:
            raise ValueError("The browser element reference is stale. Inspect the page again.")
        await locator.set_input_files(str(path))
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
