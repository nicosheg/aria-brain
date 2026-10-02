from __future__ import annotations

from contextlib import AsyncExitStack


DANGEROUS_WORDS = {
    "delete", "remove", "destroy", "drop", "send", "publish", "post", "buy",
    "purchase", "pay", "charge", "refund", "transfer", "withdraw", "invite",
    "create", "update", "edit", "write", "commit", "merge", "deploy", "submit",
    "cancel", "close", "approve", "revoke", "disable", "archive", "rename",
}


def needs_mcp_approval(tool_name: str) -> bool:
    lowered = tool_name.lower().replace("-", "_")
    return bool(set(lowered.split("_")) & DANGEROUS_WORDS)


class MCPConnectorManager:
    async def _server(self, conn: dict, require_approval):
        from agents.mcp import MCPServerStreamableHttp
        headers = {}
        if conn.get("secret"):
            headers["Authorization"] = f"Bearer {conn['secret']}"
        return MCPServerStreamableHttp(
            name=conn["name"],
            params={
                "url": conn["url"],
                "headers": headers,
                "timeout": 20,
                "sse_read_timeout": 60,
            },
            cache_tools_list=True,
            max_retry_attempts=2,
            require_approval=require_approval,
        )

    async def open_for_user(self, user_id: str, store, exit_stack: AsyncExitStack):
        try:
            import agents.mcp
        except Exception:
            return []

        servers = []
        for summary in store.list_connections(user_id):
            if summary.get("kind") not in {"mcp", "streamable_http", "http"}:
                continue
            conn = store.get_connection(user_id, summary["id"])
            if not conn:
                continue

            try:
                probe = await self._server(conn, require_approval="never")
                async with probe:
                    tools = await probe.list_tools()
                policy = {tool.name: needs_mcp_approval(tool.name) for tool in tools}
                server = await self._server(conn, require_approval=policy)
                server = await exit_stack.enter_async_context(server)
                servers.append(server)
            except Exception:
                continue
        return servers
