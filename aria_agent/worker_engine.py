from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .llm import ModelGateway
from .workers import Worker


class WorkerEngine:
    """Runs specialist worker analyses in parallel without giving them side-effect authority.

    Workers produce evidence/planning briefs. The central runtime remains the only
    component that can execute tools or cross permission boundaries.
    """

    def __init__(self, models: ModelGateway, max_workers: int = 5):
        self.models = models
        self.max_workers = max_workers

    def analyze(self, message: str, workers: list[Worker]) -> list[dict[str, Any]]:
        selected = workers[: self.max_workers]
        if not selected:
            return []

        def one(worker: Worker) -> dict[str, Any]:
            system = f"""You are ARIA's specialist worker: {worker.name}.
Mission: {worker.mission}
You are an advisory specialist inside a larger agent. You do not execute external actions.
Do not invent current facts. Say what evidence or connected tools would be needed.
Return compact JSON with:
{{"worker":"{worker.name}","objective":"...","findings":["..."],"recommended_steps":["..."],"tool_hints":["..."],"uncertainty":["..."]}}
"""
            user = f"User request:\n{message}"
            result = self.models.json(system, user, max_tokens=700)
            return result or {
                "worker": worker.name,
                "objective": worker.mission,
                "findings": [],
                "recommended_steps": [],
                "tool_hints": list(worker.tool_names),
                "uncertainty": ["No specialist model response was available."],
            }

        out: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(selected))) as pool:
            futures = {pool.submit(one, worker): worker for worker in selected}
            for future in as_completed(futures):
                try:
                    out.append(future.result())
                except Exception as exc:
                    worker = futures[future]
                    out.append({
                        "worker": worker.name,
                        "objective": worker.mission,
                        "findings": [],
                        "recommended_steps": [],
                        "tool_hints": list(worker.tool_names),
                        "uncertainty": [f"Worker failed: {type(exc).__name__}"],
                    })
        return sorted(out, key=lambda x: str(x.get("worker", "")))
