"""Compatibility bridge to the shared ARIA model gateway."""

from typing import Optional

from aria_agent.llm import ModelGateway


_gateway = ModelGateway()


def try_all_apis_parallel(prompt: str, system_prompt: str, timeout: int = 20) -> Optional[str]:
    # The legacy name is retained for compatibility; the gateway performs ordered failover.
    return _gateway.text(system_prompt, prompt, max_tokens=1000)


def call_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    return _gateway.text(system_prompt, user_prompt, max_tokens=1000)
