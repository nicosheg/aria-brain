from __future__ import annotations

import html
import os
import re
from typing import Any

import requests

from .config import get_settings


class WebSearch:
    """Public search with API-key providers and a free fallback."""

    def __init__(self):
        self.settings = get_settings()

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        for provider in (self._tavily, self._brave, self._serper, self._duckduckgo):
            try:
                results = provider(query, limit)
                if results:
                    return results
            except Exception as exc:
                print(f"[WebSearch] provider failed: {exc}")
        return []

    def _tavily(self, query: str, limit: int) -> list[dict[str, Any]]:
        key = os.getenv("TAVILY_API_KEY", "").strip()
        if not key:
            return []
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": query, "max_results": limit, "search_depth": "advanced"},
            timeout=self.settings.search_timeout_seconds,
        )
        r.raise_for_status()
        return [{"title": x.get("title",""), "url": x.get("url",""), "snippet": x.get("content","")[:1600], "source": "tavily"} for x in r.json().get("results", [])]

    def _brave(self, query: str, limit: int) -> list[dict[str, Any]]:
        key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
        if not key:
            return []
        r = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": min(limit, 20)},
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
            timeout=self.settings.search_timeout_seconds,
        )
        r.raise_for_status()
        return [{"title": x.get("title",""), "url": x.get("url",""), "snippet": x.get("description","")[:1600], "source": "brave"} for x in r.json().get("web",{}).get("results",[])]

    def _serper(self, query: str, limit: int) -> list[dict[str, Any]]:
        key = os.getenv("SERPER_API_KEY", "").strip()
        if not key:
            return []
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "num": min(limit, 20)},
            timeout=self.settings.search_timeout_seconds,
        )
        r.raise_for_status()
        return [{"title": x.get("title",""), "url": x.get("link",""), "snippet": x.get("snippet","")[:1600], "source": "serper"} for x in r.json().get("organic",[])]

    def _duckduckgo(self, query: str, limit: int) -> list[dict[str, Any]]:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "ARIA/4.0"},
            timeout=self.settings.search_timeout_seconds,
        )
        r.raise_for_status()
        body = r.text
        blocks = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', body, re.S)
        out = []
        for i, (url, title) in enumerate(blocks[:limit]):
            clean_title = re.sub(r"<.*?>", "", html.unescape(title)).strip()
            clean_snippet = re.sub(r"<.*?>", "", html.unescape(snippets[i] if i < len(snippets) else "")).strip()
            out.append({"title": clean_title, "url": html.unescape(url), "snippet": clean_snippet[:1600], "source": "duckduckgo"})
        return out


def format_sources(results: list[dict[str, Any]]) -> str:
    return "\n".join(f"{i+1}. {r.get('title','')} — {r.get('url','')}\n{r.get('snippet','')}" for i, r in enumerate(results))
