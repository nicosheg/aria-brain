from __future__ import annotations

import os
import signal
import time
from typing import Any

from aria_agent.config import get_settings
from aria_agent.runtime import AgentRuntime
from aria_agent.storage import AgentStore


_STOP = False


def _stop(*_args) -> None:
    global _STOP
    _STOP = True


def _run_job(runtime: AgentRuntime, job: dict[str, Any]) -> dict[str, Any]:
    kind = str(job.get("kind", "agent.run"))
    payload = job.get("payload") or {}
    goal = str(payload.get("goal") or payload.get("message") or "").strip()
    if not goal:
        raise ValueError("job payload has no goal")
    if kind in {"agent.run", "research", "automation", "workflow"}:
        return runtime.run(job["user_id"], goal)
    return runtime.run(
        job["user_id"],
        f"Execute this background task ({kind}) safely and report verified results only.\n\n{goal}",
    )


def main() -> None:
    global _STOP
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    settings = get_settings()
    store = AgentStore(settings.database_url)
    runtime = AgentRuntime(store)
    poll_seconds = max(1, int(os.getenv("ARIA_WORKER_POLL_SECONDS", "2")))

    while not _STOP:
        job = store.claim_job()
        if not job:
            time.sleep(poll_seconds)
            continue
        try:
            result = _run_job(runtime, job)
            store.complete_job(job["id"], result=result)
        except Exception as exc:
            store.complete_job(job["id"], error=f"{type(exc).__name__}: {exc}")
            store.audit(None, job["user_id"], "background_job.failed", {
                "job_id": job["id"], "kind": job.get("kind"), "type": type(exc).__name__,
            })


if __name__ == "__main__":
    main()
