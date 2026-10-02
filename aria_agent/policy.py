from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SAFE = "safe"
REVIEW = "review"
SENSITIVE = "sensitive"


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    risk: str
    description: str


POLICIES: dict[str, ToolPolicy] = {
    "web.search": ToolPolicy("web.search", SAFE, "Search public information."),
    "jobs.search": ToolPolicy("jobs.search", SAFE, "Search public job and opportunity sources."),
    "research.summarize": ToolPolicy("research.summarize", SAFE, "Synthesize retrieved information."),
    "memory.read": ToolPolicy("memory.read", SAFE, "Read ARIA's scoped user memory."),
    "memory.write": ToolPolicy("memory.write", REVIEW, "Write a user memory or learning."),
    "app.inspect": ToolPolicy("app.inspect", SAFE, "Inspect a connected application's available tools/data."),
    "app.read": ToolPolicy("app.read", SAFE, "Read data from a connected application."),
    "app.write": ToolPolicy("app.write", REVIEW, "Create or edit data in a connected application."),
    "app.send": ToolPolicy("app.send", SENSITIVE, "Send an external message or publish externally."),
    "app.delete": ToolPolicy("app.delete", SENSITIVE, "Delete or irreversibly change external data."),
    "app.purchase": ToolPolicy("app.purchase", SENSITIVE, "Spend money or create a financial transaction."),
    "browser.inspect": ToolPolicy("browser.inspect", SAFE, "Inspect a web page in a controlled browser."),
    "browser.act": ToolPolicy("browser.act", REVIEW, "Click, type, upload, or otherwise mutate a web application."),
}


class PolicyEngine:
    def __init__(self, autonomy_level: str = "supervised"):
        self.autonomy_level = autonomy_level

    def policy_for(self, tool_name: str, explicit_policy: str | None = None) -> ToolPolicy:
        if explicit_policy:
            return ToolPolicy(tool_name, explicit_policy, tool_name)
        return POLICIES.get(
            tool_name,
            ToolPolicy(tool_name, REVIEW, "Unknown tool; require approval before side effects."),
        )

    def requires_approval(
        self,
        tool_name: str,
        *,
        side_effect: bool = False,
        irreversible: bool = False,
        spends_money: bool = False,
        sends_external_message: bool = False,
        user_requested_autonomy: bool = False,
    ) -> bool:
        policy = self.policy_for(tool_name)
        if irreversible or spends_money or sends_external_message:
            return True
        if policy.risk == SENSITIVE:
            return True
        if policy.risk == REVIEW:
            # Explicit user request can authorize a reversible mutation only when the
            # runtime is in autonomous mode. "Supervised" is the safe product default.
            return not (self.autonomy_level == "autonomous" and user_requested_autonomy)
        return side_effect and self.autonomy_level != "autonomous"

    def validate_external_target(self, target: str, allowed_domains: tuple[str, ...]) -> bool:
        if not allowed_domains:
            return False
        target_l = target.lower()
        return any(domain in target_l for domain in allowed_domains)

    def sanitize_tool_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Never echo obvious secret fields into the model/audit summary.
        secret_keys = {"authorization", "authorization_header", "token", "access_token", "refresh_token", "api_key", "password"}
        return {
            k: ("[REDACTED]" if k.lower() in secret_keys else v)
            for k, v in payload.items()
        }
