from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Worker:
    name: str
    mission: str
    triggers: tuple[str, ...]
    tool_names: tuple[str, ...]


WORKERS: tuple[Worker, ...] = (
    Worker("research","Find, compare and synthesize reliable information.","research find out compare investigate explain".split(),("web.search","research.summarize")),
    Worker("job_finder","Find jobs, internships, gigs and practical opportunities.","job jobs internship vacancy gig work career".split(),("jobs.search","web.search")),
    Worker("opportunity_finder","Find business, freelance, creator, partnership and market opportunities.","opportunity client contract business market".split(),("web.search","research.summarize")),
    Worker("application","Tailor applications, CVs, cover letters and proposals; never submit externally without approval.","apply application cv resume cover letter proposal".split(),("jobs.search","app.read","app.write","app.send")),
    Worker("income","Turn skills, time, network and available resources into income experiments.","make money income earn monetize side hustle".split(),("web.search","jobs.search","research.summarize")),
    Worker("sales","Create offers, prospect lists, outreach sequences and follow-up plans.","sell sales offer lead prospect close".split(),("web.search","app.read","app.write","app.send")),
    Worker("communicator","Draft audience-aware personal, work and business communications.","message reply email whatsapp communicate negotiate".split(),("app.read","app.write","app.send")),
    Worker("learning","Turn goals into focused lessons, practice, feedback and improvement.","learn study practice understand course skill".split(),("web.search","research.summarize")),
    Worker("resource_optimizer","Find better ways to use the user's existing time, skills, tools and environment.","resources use optimize improve better".split(),("research.summarize","web.search","app.read")),
    Worker("personal_ops","Turn open loops into prioritized plans and next actions.","plan organize remind today next schedule".split(),("memory.read","memory.write","app.write")),
    Worker("app_operator","Inspect connected software and execute permitted native actions.","connect software app automate fill update create sync".split(),("app.inspect","app.read","app.write","app.send","app.delete")),
    Worker("data_entry","Transform trusted source data into structured application records.","enter fill import update records".split(),("app.read","app.write")),
    Worker("developer","Inspect software, diagnose failures, propose changes and prepare implementation work.","code bug build deploy test software".split(),("app.inspect","app.read","app.write")),
    Worker("finance_planning","Plan budgets and financial choices without independently moving money.","budget save spend price financial plan".split(),("research.summarize","app.read")),
    Worker("reviewer","Verify source quality, action completion and uncertainty before reporting success.","verify check review confirm worked".split(),("app.read","research.summarize")),
)


class WorkerRegistry:
    def all(self) -> list[Worker]:
        return list(WORKERS)

    def choose(self, text: str, limit: int = 4) -> list[Worker]:
        lowered = text.lower()
        scored = [(sum(2 for phrase in worker.triggers if phrase in lowered), worker) for worker in WORKERS]
        hits = [(score, worker) for score, worker in scored if score > 0]
        if not hits:
            return [next(w for w in WORKERS if w.name == "research")]
        hits.sort(key=lambda x: x[0], reverse=True)
        return [worker for _, worker in hits[:limit]]

    def manifest(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        selected = [w for w in WORKERS if not names or w.name in names]
        return [{"name":w.name,"mission":w.mission,"triggers":list(w.triggers),"tools":list(w.tool_names)} for w in selected]
