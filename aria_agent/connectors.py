from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from .security import assert_public_http_url

logger = logging.getLogger("aria.connectors")

DANGEROUS_WORDS = {
    "delete", "remove", "destroy", "drop", "send", "publish", "post", "buy",
    "purchase", "pay", "charge", "refund", "transfer", "withdraw", "invite",
    "create", "update", "edit", "write", "commit", "merge", "deploy", "submit",
    "cancel", "close", "approve", "revoke", "disable", "archive", "rename",
    "execute", "exec", "shell", "eval", "upload", "move", "replace", "apply",
}


def needs_mcp_approval(tool_name: str) -> bool:
    lowered = tool_name.lower().replace("-", "_")
    tokens = set(lowered.split("_"))
    return bool(tokens & DANGEROUS_WORDS)


class MCPConnectorManager:
    """Connect trusted user-approved MCP servers with least-privilege filtering."""

    def _auth_headers(self, conn: dict) -> dict[str, str]:
        secret = conn.get("secret", "")
        if not secret:
            return {}
        metadata = conn.get("metadata") or {}
        header_name = str(metadata.get("auth_header") or "Authorization")
        prefix = str(metadata.get("auth_prefix") or "Bearer")
        return {header_name: f"{prefix} {secret}".strip()}

    def _tool_filter(self, conn: dict):
        metadata = conn.get("metadata") or {}
        allowed = [str(x) for x in metadata.get("allowed_tools", []) if str(x).strip()]
        blocked = {str(x) for x in metadata.get("blocked_tools", []) if str(x).strip()}
        if not allowed and not blocked:
            return None
        from agents.mcp import create_static_tool_filter
        return create_static_tool_filter(
            allowed_tool_names=allowed or None,
            blocked_tool_names=list(blocked) or None,
        )

    async def _server(self, conn: dict, require_approval="never"):
        kind = conn.get("kind", "mcp")
        url = assert_public_http_url(conn["url"])
        headers = self._auth_headers(conn)
        if kind in {"mcp", "streamable_http", "http"}:
            from agents.mcp import MCPServerStreamableHttp
            return MCPServerStreamableHttp(
                name=conn["name"],
                params={
                    "url": url,
                    "headers": headers,
                    "timeout": 20,
                    "sse_read_timeout": 60,
                },
                cache_tools_list=True,
                max_retry_attempts=2,
                include_server_in_tool_names=True,
                tool_filter=self._tool_filter(conn),
                require_approval=require_approval,
            )
        if kind in {"sse", "http_sse"}:
            from agents.mcp import MCPServerSse
            return MCPServerSse(
                name=conn["name"],
                params={"url": url, "headers": headers, "timeout": 20},
                cache_tools_list=True,
                include_server_in_tool_names=True,
                tool_filter=self._tool_filter(conn),
                require_approval=require_approval,
            )
        raise ValueError(f"Unsupported MCP connection kind: {kind}")

    async def open_for_user(self, user_id: str, store, exit_stack: AsyncExitStack):
        try:
            import agents.mcp  # noqa: F401
        except Exception:
            return []

        servers = []
        for summary in store.list_connections(user_id):
            conn = store.get_connection(user_id, summary["id"])
            if not conn:
                continue
            try:
                probe = await self._server(conn)
                async with probe:
                    tools = await probe.list_tools()
                policy = {
                    tool.name: ("always" if needs_mcp_approval(tool.name) else "never")
                    for tool in tools
                }
                server = await self._server(conn, require_approval=policy)
                server = await exit_stack.enter_async_context(server)
                servers.append(server)
            except Exception as exc:
                logger.warning("MCP connection unavailable for %s: %s", summary.get("name"), type(exc).__name__)
        return servers

    async def test_connection(self, user_id: str, connection_id: str, store):
        conn = store.get_connection(user_id, connection_id)
        if not conn:
            raise KeyError("Connection not found.")
        server = await self._server(conn)
        async with server:
            tools = await server.list_tools()
            return [tool.name for tool in tools]
