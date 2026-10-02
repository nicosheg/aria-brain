"""Legacy compatibility facade for ARIA.

The old monolithic brain was replaced by aria_agent/. This module keeps older
imports working while directing execution to the new runtime.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from aria_agent.config import get_settings
from aria_agent.runtime import AgentRuntime
from aria_agent.storage import AgentStore


def generate_aria_uid(email: str) -> dict[str, str]:
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return {"error": "valid email is required"}
    return {"aria_uid": "aria_" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]}


_store = AgentStore(get_settings().database_url)
_runtime = AgentRuntime(_store)
_postgres_pool = _store._pool


def init_postgres() -> dict[str, str]:
    return {"status": "connected" if _store.durable else "memory_fallback"}


def ask(message: str, user_id: str, api: Any = None) -> str:
    return _runtime.run(user_id, message).get("reply", "I could not complete that safely.")


def ask_new(message: str, user_id: str, api: Any = None, system_prompt_override: str | None = None) -> str:
    return ask(message, user_id, api)


def save_memory(user_id: str, message: str, response: str) -> dict[str, Any]:
    key = "conversation:" + hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
    return _store.write_memory(user_id, key, f"User: {message}\nARIA: {response}", 0.4)


def get_full_history(user_id: str, limit: int = 10) -> str:
    rows = _store.read_memory(user_id, "", limit=limit)
    return "\n\n".join(row.get("content", "") for row in rows)


def get_system_health() -> dict[str, Any]:
    return {
        "status": "operational",
        "runtime": "aria_agent",
        "durable_store": _store.durable,
        "workers": len(_runtime.workers.all()),
    }


# Optional Firebase compatibility for older cognitive modules.
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        raw = os.getenv("FIREBASE_CREDENTIALS")
        if raw:
            import json
            firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
    db = firestore.client() if firebase_admin._apps else None
except Exception:
    db = None
    firestore = None
