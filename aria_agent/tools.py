from __future__ import annotations

import ast
import asyncio
import base64
import ipaddress
import json
import math
import os
import operator
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from typing import Any

import requests
from bs4 import BeautifulSoup
from agents import function_tool

try:
    from agents.tool import ToolOutputImage
except Exception:
    ToolOutputImage = None

from .browser import BrowserController
from .security import assert_public_http_url, redact_secrets
from .storage import AgentStore


def _assert_public_url(url: str) -> str:
    return assert_public_http_url(url)

# Publisher labels are heuristics, not a guarantee that a particular claim is true.
_OFFICIAL_INSTITUTIONS = {
    "cbn.gov.ng", "nigerianstat.gov.ng", "cac.gov.ng", "sec.gov.ng",
    "fccpc.gov.ng", "pencom.gov.ng", "ndic.gov.ng", "nuc.edu.ng",
    "who.int", "worldbank.org", "imf.org", "un.org", "oecd.org",
    "ilo.org", "unesco.org", "unicef.org", "fao.org", "ecowas.int",
    "ecb.europa.eu", "federalreserve.gov", "bls.gov", "census.gov",
}
_SCHOLARLY_PUBLISHERS = {
    "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "doi.org", "crossref.org",
    "nature.com", "science.org", "sciencedirect.com", "jstor.org", "arxiv.org",
    "plos.org", "bmj.com", "thelancet.com", "nejm.org", "cochranelibrary.com",
}
_EMPLOYER_HOSTED_JOB_SYSTEMS = {
    "jobs.lever.co", "boards.greenhouse.io", "jobs.ashbyhq.com",
    "apply.workable.com", "jobs.smartrecruiters.com",
}
_RECOGNIZED_LISTING_PLATFORMS = {
    "jobberman.com", "myjobmag.com", "linkedin.com", "indeed.com",
    "wellfound.com", "upwork.com", "remoteok.com", "weworkremotely.com",
    "glassdoor.com",
}

_ESTABLISHED_NEWS_PUBLISHERS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "ft.com",
    "nytimes.com", "wsj.com", "economist.com", "npr.org", "theguardian.com",
    "axios.com", "aljazeera.com", "premiumtimesng.com", "punchng.com",
    "channels.tv", "techcrunch.com", "hbr.org", "investopedia.com",
    "ourworldindata.org", "statista.com",
}
_PRIMARY_TECHNICAL_DOCUMENTATION = {
    "docs.github.com", "developer.mozilla.org", "docs.python.org",
    "fastapi.tiangolo.com", "supabase.com", "vercel.com", "render.com",
    "nextjs.org", "postgresql.org", "platform.openai.com", "openai.com",
    "developers.google.com", "cloud.google.com", "docs.aws.amazon.com",
    "learn.microsoft.com", "developer.apple.com", "pytorch.org", "tensorflow.org",
    "docs.docker.com", "kubernetes.io",
}


def _source_profile(url: str) -> dict[str, Any]:
    """Describe likely publisher class from a URL; never treat the class as proof of truth."""
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]

    def matches(domain: str) -> bool:
        return host == domain or host.endswith("." + domain)

    if parsed.scheme not in {"http", "https"} or not host:
        return {
            "publisher_domain": host,
            "publisher_class": "invalid_or_unknown",
            "publisher_assessment": "URL does not identify a public HTTP(S) publisher",
            "source_priority": 9,
        }
    if host.endswith(".gov") or host.endswith(".gov.ng") or host.endswith(".gov.uk") or host.endswith(".gov.au") or host.endswith(".gov.ca"):
        return {
            "publisher_domain": host,
            "publisher_class": "government_or_regulator_domain",
            "publisher_assessment": "Government-domain heuristic; verify this exact page, its date and its relevance",
            "source_priority": 0,
        }
    if any(matches(domain) for domain in _OFFICIAL_INSTITUTIONS):
        return {
            "publisher_domain": host,
            "publisher_class": "recognized_official_institution",
            "publisher_assessment": "Recognized institutional publisher; confirm it is primary for this specific claim",
            "source_priority": 1,
        }
    if any(matches(domain) for domain in _SCHOLARLY_PUBLISHERS):
        return {
            "publisher_domain": host,
            "publisher_class": "scholarly_publisher_or_repository",
            "publisher_assessment": "Research publisher or repository; check peer-review status, publication date and methods",
            "source_priority": 2,
        }
    if any(matches(domain) for domain in _EMPLOYER_HOSTED_JOB_SYSTEMS):
        return {
            "publisher_domain": host,
            "publisher_class": "employer_hosted_job_system",
            "publisher_assessment": "Employer application platform; verify the employer identity and that the posting is still live",
            "source_priority": 2,
        }
    if any(matches(domain) for domain in _PRIMARY_TECHNICAL_DOCUMENTATION):
        return {
            "publisher_domain": host,
            "publisher_class": "primary_technical_documentation",
            "publisher_assessment": "First-party technical or company documentation; authoritative for its own product, not automatically for unrelated claims",
            "source_priority": 1,
        }
    if any(matches(domain) for domain in _ESTABLISHED_NEWS_PUBLISHERS):
        return {
            "publisher_domain": host,
            "publisher_class": "established_news_or_research_publisher",
            "publisher_assessment": "Recognized publisher; verify byline, publication date, direct evidence and corroboration for consequential claims",
            "source_priority": 2,
        }
    if host.endswith(".edu") or host.endswith(".ac.uk") or host.endswith(".edu.ng") or host.endswith(".ac.ng"):
        return {
            "publisher_domain": host,
            "publisher_class": "academic_institution_domain",
            "publisher_assessment": "Academic domain; establish whether the page is authoritative for this claim",
            "source_priority": 2,
        }
    if any(matches(domain) for domain in _RECOGNIZED_LISTING_PLATFORMS):
        return {
            "publisher_domain": host,
            "publisher_class": "recognized_listing_platform",
            "publisher_assessment": "Third-party listing platform; independently confirm the listing and employer",
            "source_priority": 3,
        }
    return {
        "publisher_domain": host,
        "publisher_class": "third_party_unverified",
        "publisher_assessment": "Unverified publisher; open the page and corroborate material claims before relying on it",
        "source_priority": 5,
    }


def _annotate_source_result(item: dict[str, Any]) -> dict[str, Any]:
    url = str(item.get("url") or item.get("link") or "").strip()
    profile = _source_profile(url)
    return {
        "title": str(item.get("title") or "").strip(),
        "url": url,
        "snippet": str(item.get("snippet") or item.get("description") or item.get("content") or "")[:1600],
        "search_provider": str(item.get("source") or "public_web_search"),
        **profile,
    }


def _record_source(evidence_log: list[dict[str, Any]] | None, item: dict[str, Any], access: str, tool: str) -> None:
    if evidence_log is None:
        return
    url = redact_secrets(str(item.get("url") or item.get("source_url") or "").strip())
    if not url:
        return
    entry = {
        "title": str(item.get("title") or "")[:240],
        "url": url[:1600],
        "publisher_domain": str(item.get("publisher_domain") or ""),
        "publisher_class": str(item.get("publisher_class") or "third_party_unverified"),
        "source_priority": item.get("source_priority", 9),
        "access": access,
        "tool": tool,
        "retrieved_at": str(item.get("retrieved_at") or datetime.now(timezone.utc).isoformat()),
    }
    if not any(existing.get("url") == url and existing.get("access") == access for existing in evidence_log):
        if len(evidence_log) < 60:
            evidence_log.append(entry)


def _calc(expr: str) -> float:
    allowed = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed:
            return allowed[type(node.op)](visit(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in allowed:
            return allowed[type(node.op)](visit(node.left), visit(node.right))
        raise ValueError("Unsupported expression")

    value = visit(ast.parse(expr, mode="eval"))
    if not math.isfinite(float(value)):
        raise ValueError("Non-finite result")
    return float(value)


def _browser_click_needs_approval(context, args: dict[str, Any], call_id: str) -> bool:
    selector = str(args.get("selector", "")).lower()
    risky = (
        "submit", "delete", "remove", "pay", "purchase", "checkout",
        "send", "publish", "confirm", "save", "invite", "apply", "transfer",
    )
    return any(word in selector for word in risky)

def _browser_fill_needs_approval(context, args: dict[str, Any], call_id: str) -> bool:
    selector = str(args.get("selector", "")).lower()
    risky = (
        "password", "secret", "token", "otp", "one-time", "credit",
        "debit", "card", "cvv", "bank", "pin", "login", "sign-in", "signin",
    )
    return any(word in selector for word in risky)


def _safe_upload_path(user_id: str, file_name: str):
    from pathlib import Path
    from .config import settings
    root = (settings.data_dir / "uploads" / user_id).resolve()
    candidate = (root / Path(file_name).name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid upload file name.") from exc
    if not candidate.is_file():
        raise FileNotFoundError("Uploaded file not found.")
    return candidate




def build_tools(user_id: str, store: AgentStore, browser: BrowserController, browser_enabled: bool, evidence_log: list[dict[str, Any]] | None = None):
    async def _search_public(query: str, limit: int = 6) -> list[dict[str, str]]:
        q = (query or "").strip()
        lim = max(1, min(int(limit), 12))
        tavily = os.getenv("TAVILY_API_KEY", "").strip()
        if tavily:
            try:
                response = await asyncio.to_thread(
                    requests.post,
                    "https://api.tavily.com/search",
                    json={"api_key": tavily, "query": q, "max_results": lim, "search_depth": "advanced"},
                    timeout=15,
                )
                response.raise_for_status()
                items = response.json().get("results", [])
                if items:
                    return [{"title": x.get("title",""), "url": x.get("url",""), "snippet": x.get("content","")[:1600], "source":"tavily"} for x in items]
            except Exception:
                pass

        brave = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
        if brave:
            try:
                response = await asyncio.to_thread(
                    requests.get,
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": q, "count": lim},
                    headers={"X-Subscription-Token": brave, "Accept": "application/json"},
                    timeout=15,
                )
                response.raise_for_status()
                items = response.json().get("web", {}).get("results", [])
                if items:
                    return [{"title": x.get("title",""), "url": x.get("url",""), "snippet": x.get("description","")[:1600], "source":"brave"} for x in items]
            except Exception:
                pass

        serper = os.getenv("SERPER_API_KEY", "").strip()
        if serper:
            try:
                response = await asyncio.to_thread(
                    requests.post,
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": serper, "Content-Type": "application/json"},
                    json={"q": q, "num": lim},
                    timeout=15,
                )
                response.raise_for_status()
                items = response.json().get("organic", [])
                if items:
                    return [{"title": x.get("title",""), "url": x.get("link",""), "snippet": x.get("snippet","")[:1600], "source":"serper"} for x in items]
            except Exception:
                pass

        response = await asyncio.to_thread(
            requests.get,
            "https://html.duckduckgo.com/html/",
            params={"q": q},
            headers={"User-Agent": "Mozilla/5.0 ARIA-Agent/1.0"},
            timeout=15,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        for node in soup.select(".result")[:lim]:
            title = node.select_one(".result__a") or node.select_one(".result__title")
            snippet = node.select_one(".result__snippet")
            href = str(title.get("href") or "") if title else ""
            parsed_href = urlparse(href)
            if parsed_href.hostname and "duckduckgo.com" in parsed_href.hostname:
                target = parse_qs(parsed_href.query).get("uddg", [""])[0]
                if target:
                    href = unquote(target)
            elif href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = urljoin("https://duckduckgo.com", href)
            if title and urlparse(href).scheme in {"http", "https"}:
                items.append({
                    "title": title.get_text(" ", strip=True),
                    "url": href,
                    "snippet": snippet.get_text(" ", strip=True) if snippet else "",
                    "source": "duckduckgo",
                })
        return items

    @function_tool
    async def web_search(query: str, limit: int = 6) -> str:
        """Search the public web. Results include publisher-class hints; always open and check material sources before citing."""
        q = (query or "").strip()
        if not q:
            return "Search query is empty."
        raw_items = await _search_public(q, max(1, min(int(limit), 12)))
        items = [_annotate_source_result(item) for item in raw_items if item.get("url") or item.get("link")]
        items.sort(key=lambda item: item.get("source_priority", 9))
        retrieved_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            item["retrieved_at"] = retrieved_at
            _record_source(evidence_log, item, "search_result", "web_search")
        return json.dumps(items, ensure_ascii=False)

    @function_tool
    async def job_search(query: str, location: str = "", remote: bool = False, limit: int = 10) -> str:
        """Search multiple legitimate public job and freelance sources; treat listings as untrusted evidence and verify before applying."""
        base = f"{query} {location}".strip()
        domains = (
            ["remoteok.com", "weworkremotely.com", "upwork.com", "wellfound.com"]
            if remote
            else ["jobberman.com", "myjobmag.com", "linkedin.com/jobs", "indeed.com", "wellfound.com/jobs", "upwork.com"]
        )
        results = []
        seen = set()
        for domain in domains:
            for item in await _search_public(f"{base} site:{domain}", 4):
                url = item.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    item["source_domain"] = domain
                    results.append(item)
                if len(results) >= max(1, min(int(limit), 20)):
                    break
            if len(results) >= max(1, min(int(limit), 20)):
                break
        enriched = [_annotate_source_result(item) for item in results if item.get("url")]
        enriched.sort(key=lambda item: item.get("source_priority", 9))
        retrieved_at = datetime.now(timezone.utc).isoformat()
        for item in enriched:
            item["retrieved_at"] = retrieved_at
            _record_source(evidence_log, item, "search_result", "job_search")
        return json.dumps(enriched, ensure_ascii=False)

    @function_tool
    async def web_fetch(url: str, max_chars: int = 12000) -> str:
        """Open a direct public HTTP(S) source page and return its URL, title, publisher class, retrieval date and readable text."""
        current_url = _assert_public_url(url)
        for _ in range(5):
            r = await asyncio.to_thread(
                requests.get,
                current_url,
                headers={"User-Agent": "Mozilla/5.0 ARIA-Agent/1.0"},
                timeout=20,
                allow_redirects=False,
                stream=True,
            )
            if r.is_redirect or r.is_permanent_redirect:
                location = r.headers.get("Location", "").strip()
                if not location:
                    raise ValueError("Redirect response did not contain a location.")
                current_url = _assert_public_url(urljoin(current_url, location))
                continue
            r.raise_for_status()
            chunks = []
            total = 0
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > 5 * 1024 * 1024:
                    raise ValueError("Fetched page is larger than 5MB.")
                chunks.append(chunk)
            raw_body = b"".join(chunks)
            break
        else:
            raise ValueError("Too many redirects.")

        soup = BeautifulSoup(raw_body, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
        page_text = " ".join(soup.get_text(" ", strip=True).split())
        retrieved_at = datetime.now(timezone.utc).isoformat()
        record = {
            "source_url": current_url,
            "title": page_title[:300],
            **_source_profile(current_url),
            "retrieved_at": retrieved_at,
            "content": page_text[:max(1000, min(max_chars, 30000))],
        }
        _record_source(evidence_log, record, "opened_page", "web_fetch")
        return json.dumps(record, ensure_ascii=False)

    @function_tool
    def calculator(expression: str) -> str:
        """Calculate a basic arithmetic expression safely."""
        return str(_calc(expression))

    @function_tool
    def list_uploaded_files() -> str:
        """List files in the user private ARIA workspace."""
        from pathlib import Path
        from .config import settings
        root = (settings.data_dir / "uploads" / user_id).resolve()
        if not root.exists():
            return "No uploaded files."
        items = []
        for path in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if path.is_file():
                items.append({"name": path.name, "bytes": path.stat().st_size})
        return json.dumps(items[:200], ensure_ascii=False)

    @function_tool
    def read_uploaded_file(file_name: str, max_chars: int = 50000) -> Any:
        """Read a user upload or return an image as model-visible visual input."""
        from pathlib import Path
        from .config import settings
        root = (settings.data_dir / "uploads" / user_id).resolve()
        candidate = (root / Path(file_name).name).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Invalid file name.") from exc
        if not candidate.is_file():
            raise FileNotFoundError("Uploaded file not found.")
        suffix = candidate.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"} and ToolOutputImage is not None:
            if candidate.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("Image is larger than 8MB; upload a smaller image for visual analysis.")
            encoded = base64.b64encode(candidate.read_bytes()).decode("ascii")
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}[suffix.lstrip(".")]
            return ToolOutputImage(image_url=f"data:{mime};base64,{encoded}", detail="high")
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(candidate))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            return text[:max(1000, min(max_chars, 100000))]
        try:
            return candidate.read_text("utf-8")[:max(1000, min(max_chars, 100000))]
        except UnicodeDecodeError as exc:
            raise ValueError("This binary file type is not readable as text.") from exc

    @function_tool
    def remember(content: str, kind: str = "fact", importance: float = 0.8) -> str:
        """Persist a useful fact, preference, goal, constraint or decision for this user."""
        from .security import redact_secrets
        safe_content = redact_secrets(content)
        return f"Remembered as {store.add_memory(user_id, kind, safe_content, importance=float(importance))}."

    @function_tool
    def search_memory(query: str, limit: int = 8) -> str:
        """Search ARIA's durable user memory before asking for information again."""
        return json.dumps(store.search_memory(user_id, query, max(1, min(limit, 20))), ensure_ascii=False)

    @function_tool
    def enqueue_background_job(
        kind: str,
        goal: str,
        payload_json: str = "{}",
        delay_seconds: int = 0,
        repeat_seconds: int = 0,
    ) -> str:
        """Queue a long-running goal; optionally delay or repeat it after successful completion."""
        try:
            parsed_payload = json.loads(payload_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("payload_json must be valid JSON.") from exc
        if not isinstance(parsed_payload, dict):
            raise ValueError("payload_json must decode to an object.")
        body = {
            k: redact_secrets(str(v)) if isinstance(v, str) else v
            for k, v in parsed_payload.items()
        }
        body["goal"] = redact_secrets(goal)
        if repeat_seconds > 0:
            body["repeat_seconds"] = int(min(repeat_seconds, 31 * 24 * 3600))
        run_after = (
            datetime.now(timezone.utc) + timedelta(seconds=max(0, delay_seconds))
        ).isoformat()
        job_id = store.enqueue_job(user_id, kind, body, run_after=run_after)
        return f"Queued background job {job_id}."

    async def _browser_ready():
        if not browser_enabled:
            raise RuntimeError("Browser automation is disabled.")
        return True

    async def _browser_ref_needs_approval_for_user(context, args: dict[str, Any], call_id: str) -> bool:
        ref = str(args.get("ref", "")).strip()
        if not ref:
            return True
        return await browser.ref_needs_approval(user_id, ref)

    @function_tool
    async def browser_open(url: str) -> str:
        """Open a website in ARIA's persistent browser session and inspect it."""
        await _browser_ready()
        return await browser.navigate(user_id, url)

    @function_tool
    async def browser_inspect_elements() -> str:
        """Inspect the current page and return safe element references for links, buttons and form fields."""
        await _browser_ready()
        return await browser.inspect(user_id)

    @function_tool(needs_approval=_browser_ref_needs_approval_for_user)
    async def browser_click_ref(ref: str) -> str:
        """Click an element by the ARIA browser reference returned by browser_inspect_elements."""
        await _browser_ready()
        return await browser.click_ref(user_id, ref)

    @function_tool(needs_approval=_browser_ref_needs_approval_for_user)
    async def browser_fill_ref(ref: str, value: str) -> str:
        """Fill a text field by its ARIA browser reference."""
        await _browser_ready()
        return await browser.fill_ref(user_id, ref, value)

    @function_tool(needs_approval=_browser_ref_needs_approval_for_user)
    async def browser_select_ref(ref: str, value: str) -> str:
        """Select an option in a select element by its ARIA browser reference."""
        await _browser_ready()
        return await browser.select_ref(user_id, ref, value)

    @function_tool(needs_approval=True)
    async def browser_upload_ref(ref: str, file_name: str) -> str:
        """Upload a private ARIA workspace file to a browser file input. Approval is always required."""
        await _browser_ready()
        path = _safe_upload_path(user_id, file_name)
        return await browser.upload_ref(user_id, ref, str(path))

    @function_tool
    async def browser_inspect() -> str:
        """Inspect the current browser page as text, including title, URL and visible text."""
        await _browser_ready()
        return await browser.snapshot(user_id)

    @function_tool
    async def browser_screenshot() -> Any:
        """Take a screenshot of the current browser page for visual verification."""
        await _browser_ready()
        b64 = await browser.screenshot(user_id)
        if ToolOutputImage is not None:
            return ToolOutputImage(image_url=f"data:image/png;base64,{b64}", detail="high")
        return f"SCREENSHOT_CAPTURED_BASE64:{b64[:100]}..."

    @function_tool(needs_approval=_browser_click_needs_approval)
    async def browser_click(selector: str) -> str:
        """Click a CSS selector in the current page. Risky-looking targets require approval."""
        await _browser_ready()
        return await browser.click(user_id, selector)

    @function_tool(needs_approval=_browser_fill_needs_approval)
    async def browser_fill(selector: str, value: str) -> str:
        """Fill a form control by CSS selector."""
        await _browser_ready()
        return await browser.fill(user_id, selector, value)

    @function_tool(needs_approval=_browser_fill_needs_approval)
    async def browser_press(selector: str, key: str) -> str:
        """Press a keyboard key on a selected form control."""
        await _browser_ready()
        return await browser.press(user_id, selector, key)

    @function_tool(needs_approval=True)
    async def browser_submit(selector: str) -> str:
        """Submit a form. This always requires human approval before the side effect."""
        await _browser_ready()
        return await browser.submit(user_id, selector)

    return [
        web_search, job_search, web_fetch, calculator, remember, search_memory, enqueue_background_job, list_uploaded_files, read_uploaded_file,
        browser_open, browser_inspect, browser_inspect_elements, browser_screenshot,
        browser_click, browser_click_ref, browser_fill, browser_fill_ref, browser_select_ref,
        browser_press, browser_submit, browser_upload_ref,
    ]
