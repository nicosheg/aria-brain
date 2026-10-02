from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any
import ipaddress
import socket
import threading
from urllib.parse import urlparse

import requests

from .config import get_settings


def _fernet():
    key = get_settings().connector_encryption_key
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        try:
            return Fernet(key.encode())
        except Exception:
            return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))
    except ImportError:
        return None


def _contains_secret(value: Any, key_name: str = "") -> bool:
    sensitive = {
        "token","access_token","refresh_token","password","api_key","client_secret",
        "authorization","cookie","cookies","secret","cdp_url","webhook_secret",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in sensitive or _contains_secret(child, key):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_secret(child, key_name) for child in value)
    return key_name.lower() in sensitive


def protect_config(config: dict[str, Any]) -> dict[str, Any]:
    f = _fernet()
    if not f:
        if _contains_secret(config):
            raise RuntimeError("ARIA_CONNECTOR_ENCRYPTION_KEY is required to store connector secrets.")
        return config
    return {"encrypted": True, "value": f.encrypt(json.dumps(config).encode()).decode()}


def reveal_config(config: dict[str, Any]) -> dict[str, Any]:
    if not config.get("encrypted"):
        return config
    f = _fernet()
    if not f:
        raise RuntimeError("Connector encryption key is unavailable.")
    return json.loads(f.decrypt(config["value"].encode()).decode())



def _is_private_host(hostname: str) -> bool:
    host = (hostname or "").strip().lower()
    if not host or host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)}
    except Exception:
        return True
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return True
    return False


def _validate_public_url(url: str, allowed_domains: list[str] | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PermissionError("connector target must be an HTTP(S) URL")
    hostname = parsed.hostname.lower()
    if allowed_domains:
        domains = [str(x).lower().lstrip(".") for x in allowed_domains]
        if not any(hostname == d or hostname.endswith("." + d) for d in domains):
            raise PermissionError("connector target is outside the configured domain allow-list")
    if _is_private_host(hostname) and not get_settings().allow_private_connectors:
        raise PermissionError("connector target resolves to a private or local network address")
    return url


class Connector:
    def __init__(self, row: dict[str, Any]):
        self.row = row
        self.config = reveal_config(row.get("config_json") or {})
        self.base_url = (row.get("base_url") or "").rstrip("/")

    @property
    def name(self) -> str:
        return self.row["name"]

    def list_tools(self) -> list[dict[str, Any]]:
        return []

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class RESTConnector(Connector):
    def list_tools(self) -> list[dict[str, Any]]:
        return list(self.config.get("actions", []))

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        action = next((a for a in self.list_tools() if a.get("name") == tool_name), None)
        if not action:
            raise KeyError(f"REST action not found: {tool_name}")
        method = action.get("method", "GET").upper()
        path = action.get("path", "/")
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        if path.startswith("http"):
            base_host = (urlparse(self.base_url).hostname or "").lower()
            target_host = (urlparse(url).hostname or "").lower()
            allowed = {str(x).lower().lstrip(".") for x in self.allowed_domains}
            if base_host and target_host != base_host and target_host not in allowed:
                raise PermissionError("REST action target is outside its connector domain")
        url = _validate_public_url(url, self.allowed_domains or None)
        headers = dict(action.get("headers", {}))
        auth_env = action.get("auth_env")
        if auth_env:
            token = os.getenv(auth_env, "")
            if token:
                headers["Authorization"] = headers.get("Authorization", f"Bearer {token}")
        response = requests.request(
            method,
            url,
            headers=headers,
            json=arguments if method not in {"GET","DELETE"} else None,
            params=arguments if method in {"GET","DELETE"} else None,
            timeout=get_settings().search_timeout_seconds,
        )
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError:
            data = response.text
        return {"status_code": response.status_code, "data": data}


class MCPConnector(Connector):
    """Supports modern stateless MCP and legacy session-based MCP over HTTP."""

    def __init__(self, row: dict[str, Any]):
        super().__init__(row)
        self._legacy_session = None

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        token = self.config.get("access_token") or os.getenv(self.config.get("auth_env", ""), "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _decode(self, response: requests.Response) -> dict[str, Any]:
        raw = response.text.strip()
        if raw.startswith("data:"):
            chunks = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
            raw = chunks[-1] if chunks else "{}"
        data = json.loads(raw or "{}")
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "MCP error"))
        return data.get("result", data)

    def _modern(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = self._auth_headers()
        headers["MCP-Protocol-Version"] = self.config.get("protocol_version", "2026-07-28")
        headers["Mcp-Method"] = method
        if method == "tools/call":
            headers["Mcp-Name"] = params.get("name", "")
        response = requests.post(
            _validate_public_url(self.base_url, self.allowed_domains or None),
            headers=headers,
            json={"jsonrpc":"2.0","id":1,"method":method,"params":params},
            timeout=get_settings().search_timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"MCP HTTP {response.status_code}: {response.text[:500]}")
        return self._decode(response)

    def _legacy_init(self) -> None:
        response = requests.post(
            _validate_public_url(self.base_url, self.allowed_domains or None),
            headers=self._auth_headers(),
            json={"jsonrpc":"2.0","id":1,"method":"initialize","params":{
                "protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"ARIA","version":"4.0.0"}}},
            timeout=get_settings().search_timeout_seconds,
        )
        response.raise_for_status()
        self._legacy_session = response.headers.get("Mcp-Session-Id")
        self._decode(response)
        headers = self._auth_headers()
        if self._legacy_session:
            headers["Mcp-Session-Id"] = self._legacy_session
        requests.post(_validate_public_url(self.base_url, self.allowed_domains or None), headers=headers, json={"jsonrpc":"2.0","method":"notifications/initialized"}, timeout=get_settings().search_timeout_seconds)

    def _legacy(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._legacy_session:
            self._legacy_init()
        headers = self._auth_headers()
        headers["Mcp-Session-Id"] = self._legacy_session
        response = requests.post(_validate_public_url(self.base_url, self.allowed_domains or None), headers=headers, json={"jsonrpc":"2.0","id":2,"method":method,"params":params}, timeout=get_settings().search_timeout_seconds)
        response.raise_for_status()
        return self._decode(response)

    def list_tools(self) -> list[dict[str, Any]]:
        try:
            result = self._modern("tools/list", {})
        except Exception:
            result = self._legacy("tools/list", {})
        return result.get("tools", result.get("result", {}).get("tools", []))

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._modern("tools/call", {"name":tool_name,"arguments":arguments})
        except Exception:
            return self._legacy("tools/call", {"name":tool_name,"arguments":arguments})


class BrowserConnector(Connector):
    """Optional Playwright browser bridge with explicit domain allow-listing."""

    def _allowed(self, url: str) -> bool:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        allowed = [str(x).lower().lstrip(".") for x in self.config.get("allowed_domains", [])]
        return bool(host and allowed and any(host == d or host.endswith("." + d) for d in allowed))

    def _page(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed.") from exc
        if not hasattr(self, "_pw"):
            self._pw = sync_playwright().start()
            cdp_url = self.config.get("cdp_url")
            if cdp_url:
                self._browser = self._pw.chromium.connect_over_cdp(cdp_url)
                contexts = self._browser.contexts or [self._browser.new_context()]
                self._context = contexts[0]
                pages = self._context.pages
                self._page_obj = pages[0] if pages else self._context.new_page()
            else:
                self._browser = self._pw.chromium.launch(headless=bool(self.config.get("headless", True)))
                self._context = self._browser.new_context()
                self._page_obj = self._context.new_page()
        return self._page_obj

    def _check_current_url(self, page) -> None:
        if page.url.startswith(("about:", "data:")):
            return
        if not self._allowed(page.url):
            try:
                page.go_back(wait_until="domcontentloaded", timeout=3000)
            except Exception:
                pass
            raise PermissionError("Browser navigation left ARIA's allowed domain set.")

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name":"browser.snapshot","description":"Inspect the current page, forms, links and controls.","risk":"safe","inputSchema":{"type":"object"}},
            {"name":"browser.navigate","description":"Open an allowed URL.","risk":"review","inputSchema":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}},
            {"name":"browser.click","description":"Click a button, link or element.","risk":"review","inputSchema":{"type":"object","properties":{"selector":{"type":"string"},"text":{"type":"string"}}}},
            {"name":"browser.fill","description":"Fill a text input or textarea.","risk":"review","inputSchema":{"type":"object","properties":{"selector":{"type":"string"},"label":{"type":"string"},"value":{"type":"string"}},"required":["value"]}},
            {"name":"browser.select","description":"Select a form option.","risk":"review","inputSchema":{"type":"object","properties":{"selector":{"type":"string"},"label":{"type":"string"},"value":{"type":"string"}},"required":["value"]}},
            {"name":"browser.press","description":"Press a keyboard key.","risk":"review","inputSchema":{"type":"object","properties":{"selector":{"type":"string"},"key":{"type":"string"}},"required":["key"]}},
            {"name":"browser.back","description":"Go back one page.","risk":"review","inputSchema":{"type":"object"}},
        ]

    def _locator(self, page, arguments: dict[str, Any]):
        if arguments.get("selector"):
            return page.locator(arguments["selector"]).first
        if arguments.get("text"):
            return page.get_by_text(arguments["text"], exact=True).first
        if arguments.get("label"):
            return page.get_by_label(arguments["label"], exact=True).first
        return None

    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        page = self._page()
        self._check_current_url(page)

        if tool_name == "browser.snapshot":
            return {
                "url": page.url,
                "title": page.title(),
                "content_is_untrusted": True,
                "text": page.locator("body").inner_text(timeout=5000)[:12000],
                "forms": page.locator("input,textarea,select").evaluate_all(
                    "els => els.slice(0, 60).map(e => ({tag:e.tagName.toLowerCase(),name:e.name||'',id:e.id||'',type:e.type||'',placeholder:e.placeholder||'',aria:e.getAttribute('aria-label')||''}))"
                ),
                "links": page.locator("a").evaluate_all(
                    "els => els.slice(0, 80).map(e => ({text:(e.innerText||'').trim().slice(0,160),href:e.href||''}))"
                ),
                "buttons": page.locator("button,[role=button]").evaluate_all(
                    "els => els.slice(0, 60).map(e => (e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,160)).filter(Boolean)"
                ),
            }

        if tool_name == "browser.navigate":
            url = str(arguments.get("url", "")).strip()
            if not self._allowed(url):
                raise PermissionError("Target URL is outside the connector allowed domains.")
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            self._check_current_url(page)
            return {"url":page.url,"title":page.title()}

        if tool_name == "browser.click":
            loc = self._locator(page, arguments)
            if not loc:
                raise ValueError("click requires selector, text, or label")
            loc.click(timeout=10000)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            self._check_current_url(page)
            return {"url":page.url,"title":page.title()}

        if tool_name == "browser.fill":
            loc = self._locator(page, arguments)
            if not loc:
                raise ValueError("fill requires selector, text, or label")
            loc.fill(str(arguments.get("value","")), timeout=10000)
            return {"filled":True,"field":arguments.get("selector") or arguments.get("label") or arguments.get("text")}

        if tool_name == "browser.select":
            loc = self._locator(page, arguments)
            if not loc:
                raise ValueError("select requires selector or label")
            loc.select_option(str(arguments.get("value","")), timeout=10000)
            return {"selected":True}

        if tool_name == "browser.press":
            loc = self._locator(page, arguments) or page.locator("body")
            loc.press(str(arguments.get("key","Enter")), timeout=10000)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            self._check_current_url(page)
            return {"pressed":arguments.get("key"),"url":page.url}

        if tool_name == "browser.back":
            page.go_back(wait_until="domcontentloaded", timeout=10000)
            self._check_current_url(page)
            return {"url":page.url,"title":page.title()}

        raise KeyError(f"Browser tool not found: {tool_name}")

    def close(self) -> None:
        browser = getattr(self, "_browser", None)
        playwright = getattr(self, "_pw", None)
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if playwright:
            try:
                playwright.stop()
            except Exception:
                pass


class ConnectorManager:
    def __init__(self, store):
        self.store = store
        self._instances: dict[str, Connector] = {}
        self._locks: dict[str, threading.RLock] = {}

    def register(self, user_id: str, name: str, connector_type: str, base_url: str, config: dict[str, Any]) -> dict[str, Any]:
        if connector_type not in {"mcp","rest","browser"}:
            raise ValueError("connector_type must be mcp or rest")
        if not name.strip() or (connector_type != "browser" and not base_url.strip()):
            raise ValueError("name and base_url are required")
        connector_id = hashlib.sha256(f"{user_id}:{name.strip().lower()}".encode()).hexdigest()[:24]
        row = {"id":connector_id,"user_id":user_id,"name":name.strip(),"connector_type":connector_type,"base_url":base_url.strip().rstrip("/"),"config_json":protect_config(config)}
        saved = self.store.upsert_connector(row)
        old = self._instances.pop(saved["id"], None)
        self._locks.pop(saved["id"], None)
        if old:
            close = getattr(old, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        return saved

    def delete(self, connector_id: str, user_id: str) -> bool:
        deleted = self.store.delete_connector(connector_id, user_id)
        if deleted:
            old = self._instances.pop(connector_id, None)
            self._locks.pop(connector_id, None)
            if old:
                close = getattr(old, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass
        return deleted

    def _rows(self, user_id: str) -> list[dict[str, Any]]:
        return self.store.list_connectors(user_id)

    def get(self, connector_id: str, user_id: str) -> Connector:
        row = next((r for r in self._rows(user_id) if r["id"] == connector_id), None)
        if not row:
            raise KeyError("connector not found")
        if connector_id not in self._instances:
            if row["connector_type"] == "mcp":
                self._instances[connector_id] = MCPConnector(row)
            elif row["connector_type"] == "browser":
                self._instances[connector_id] = BrowserConnector(row)
            else:
                self._instances[connector_id] = RESTConnector(row)
            self._locks[connector_id] = threading.RLock()
        return self._instances[connector_id]

    def tools(self, user_id: str) -> list[dict[str, Any]]:
        all_tools = []
        for row in self._rows(user_id):
            try:
                connector = self.get(row["id"], user_id)
                for tool in connector.list_tools():
                    item = dict(tool)
                    item["connector_id"] = row["id"]
                    item["connector"] = row["name"]
                    all_tools.append(item)
            except Exception as exc:
                all_tools.append({"name":f"{row['name']}.connection_error","description":f"Connector unavailable: {type(exc).__name__}","connector_id":row["id"],"connector":row["name"],"error":True})
        return all_tools

    def call(self, user_id: str, connector_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        connector = self.get(connector_id, user_id)
        with self._locks[connector_id]:
            return connector.call(tool_name, arguments)

    def close_all(self) -> None:
        for connector in list(self._instances.values()):
            close = getattr(connector, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        self._instances.clear()
        self._locks.clear()
