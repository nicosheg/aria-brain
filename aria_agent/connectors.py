from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

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


def protect_config(config: dict[str, Any]) -> dict[str, Any]:
    f = _fernet()
    secret_names = {"token","access_token","refresh_token","password","api_key"}
    if not f:
        if any(k.lower() in secret_names for k in config):
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
            self.base_url,
            headers=headers,
            json={"jsonrpc":"2.0","id":1,"method":method,"params":params},
            timeout=get_settings().search_timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"MCP HTTP {response.status_code}: {response.text[:500]}")
        return self._decode(response)

    def _legacy_init(self) -> None:
        response = requests.post(
            self.base_url,
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
        requests.post(self.base_url, headers=headers, json={"jsonrpc":"2.0","method":"notifications/initialized"}, timeout=get_settings().search_timeout_seconds)

    def _legacy(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._legacy_session:
            self._legacy_init()
        headers = self._auth_headers()
        headers["Mcp-Session-Id"] = self._legacy_session
        response = requests.post(self.base_url, headers=headers, json={"jsonrpc":"2.0","id":2,"method":method,"params":params}, timeout=get_settings().search_timeout_seconds)
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


class ConnectorManager:
    def __init__(self, store):
        self.store = store

    def register(self, user_id: str, name: str, connector_type: str, base_url: str, config: dict[str, Any]) -> dict[str, Any]:
        if connector_type not in {"mcp","rest"}:
            raise ValueError("connector_type must be mcp or rest")
        if not name.strip() or not base_url.strip():
            raise ValueError("name and base_url are required")
        connector_id = hashlib.sha256(f"{user_id}:{name.strip().lower()}".encode()).hexdigest()[:24]
        row = {"id":connector_id,"user_id":user_id,"name":name.strip(),"connector_type":connector_type,"base_url":base_url.strip().rstrip("/"),"config_json":protect_config(config)}
        return self.store.upsert_connector(row)

    def delete(self, connector_id: str, user_id: str) -> bool:
        return self.store.delete_connector(connector_id, user_id)

    def _rows(self, user_id: str) -> list[dict[str, Any]]:
        return self.store.list_connectors(user_id)

    def get(self, connector_id: str, user_id: str) -> Connector:
        row = next((r for r in self._rows(user_id) if r["id"] == connector_id), None)
        if not row:
            raise KeyError("connector not found")
        return MCPConnector(row) if row["connector_type"] == "mcp" else RESTConnector(row)

    def tools(self, user_id: str) -> list[dict[str, Any]]:
        all_tools = []
        for row in self._rows(user_id):
            try:
                connector = MCPConnector(row) if row["connector_type"] == "mcp" else RESTConnector(row)
                for tool in connector.list_tools():
                    item = dict(tool)
                    item["connector_id"] = row["id"]
                    item["connector"] = row["name"]
                    all_tools.append(item)
            except Exception as exc:
                all_tools.append({"name":f"{row['name']}.connection_error","description":f"Connector unavailable: {type(exc).__name__}","connector_id":row["id"],"connector":row["name"],"error":True})
        return all_tools

    def call(self, user_id: str, connector_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.get(connector_id, user_id).call(tool_name, arguments)
