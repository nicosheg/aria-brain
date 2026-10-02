from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Worker:
    name: str
    mission: str
    triggers: tuple[str, ...]
    tool_names: tuple[str, ...]


def _w(name: str, mission: str, triggers: str, tools: tuple[str, ...]) -> Worker:
    return Worker(name, mission, tuple(triggers.split("|")), tools)


WORKERS: tuple[Worker, ...] = (
    _w("research", "Find, compare and synthesize reliable information before decisions.", "research|find out|compare|investigate|explain", ("web.search","research.summarize")),
    _w("job_finder", "Find jobs, internships, gigs, apprenticeships and practical opportunities.", "job|jobs|internship|vacancy|gig|work|career", ("jobs.search","web.search")),
    _w("job_creator", "Help an employer turn a need into a clear role, job description and hiring workflow.", "create job|hire|hiring|job description|vacancy", ("research.summarize","app.write","app.send")),
    _w("opportunity_finder", "Find business, freelance, creator, partnership and market opportunities.", "opportunity|client|contract|business opportunity|partnership|market", ("web.search","research.summarize")),
    _w("application", "Tailor CVs, cover letters, proposals and applications; never submit externally without approval.", "apply|application|cv|resume|cover letter|proposal", ("jobs.search","app.read","app.write","app.send")),
    _w("income", "Turn skills, time, network and available resources into realistic income experiments.", "make money|income|earn|money|monetize|side hustle", ("web.search","jobs.search","research.summarize")),
    _w("microbusiness", "Design small businesses around a user's existing resources, local demand and constraints.", "small business|start business|business idea|sell something|startup", ("web.search","research.summarize","app.write")),
    _w("sales", "Create offers, prospect lists, outreach sequences and follow-up plans.", "sell|sales|offer|lead|prospect|close", ("web.search","app.read","app.write","app.send")),
    _w("marketing", "Turn a product or service into a clear message, positioning and repeatable acquisition system.", "marketing|market|brand|position|promotion|customers", ("web.search","research.summarize","app.write")),
    _w("communicator", "Draft audience-aware personal, work and business communications.", "message|reply|email|whatsapp|communicate|negotiate", ("app.read","app.write","app.send")),
    _w("negotiator", "Prepare options, scripts and tradeoffs for negotiations without making unauthorized commitments.", "negotiate|negotiation|price|deal|terms|bargain", ("research.summarize","app.read","app.write","app.send")),
    _w("customer_success", "Improve retention, onboarding, follow-up and customer care.", "customer|retention|onboarding|follow up|support", ("app.read","app.write","app.send")),
    _w("learning", "Turn goals into focused lessons, practice, feedback and improvement.", "learn|study|practice|understand|course|skill", ("web.search","research.summarize")),
    _w("study_coach", "Build study plans, explain difficult topics and create practice loops.", "exam|assignment|study plan|revision|math|school", ("web.search","research.summarize","memory.write")),
    _w("resource_optimizer", "Find better ways to use the user's existing time, skills, tools and environment.", "resources|use what i have|optimize|improve|better|1% better", ("research.summarize","web.search","app.read")),
    _w("personal_ops", "Turn open loops into prioritized plans, checklists and next actions.", "plan|organize|remind|today|next|schedule", ("memory.read","memory.write","app.write")),
    _w("app_operator", "Inspect connected software and execute permitted native actions.", "connect|software|app|automate|fill|update|create|sync", ("app.inspect","app.read","app.write","app.send","app.delete")),
    _w("data_entry", "Transform trusted source data into correctly structured application records.", "enter|fill|import|update records|data entry", ("app.read","app.write")),
    _w("developer", "Inspect software, diagnose failures, propose changes and prepare implementation work.", "code|bug|build|deploy|test|software", ("app.inspect","app.read","app.write")),
    _w("qa_reviewer", "Test workflows, reproduce failures and verify fixes before reporting success.", "test|qa|verify fix|regression|broken|failed", ("app.inspect","app.read","app.write","research.summarize")),
    _w("market_research", "Understand demand, competitors, prices, customers and market gaps.", "competitors|demand|market research|pricing|customer research", ("web.search","research.summarize")),
    _w("content", "Create useful content plans, drafts, repurposing and publishing workflows.", "content|post|caption|video|article|social media", ("web.search","research.summarize","app.write","app.send")),
    _w("portfolio", "Turn experience and proof into a portfolio, profile, case study or proposal.", "portfolio|profile|case study|personal brand|proof", ("app.read","app.write","research.summarize")),
    _w("finance_planning", "Plan budgets, pricing and financial choices without independently moving money.", "budget|save|spend|price|financial plan", ("research.summarize","app.read")),
    _w("admin_ops", "Handle repetitive operational tasks, records, checklists and coordination.", "admin|operations|ops|records|coordination|routine task", ("app.read","app.write")),
    _w("reviewer", "Verify source quality, action completion and uncertainty before reporting success.", "verify|check|review|confirm|did it work", ("app.read","research.summarize")),
    _w("automation", "Translate repeatable business or personal processes into safe event-driven workflows.", "automate|automation|when this happens|trigger|workflow", ("app.inspect","app.read","app.write","app.send","app.delete")),
)


class WorkerRegistry:
    def all(self) -> list[Worker]:
        return list(WORKERS)

    def choose(self, text: str, limit: int = 5) -> list[Worker]:
        lowered = text.lower()
        scored = []
        for worker in WORKERS:
            score = sum(2 for phrase in worker.triggers if phrase in lowered)
            if score:
                scored.append((score, worker))
        if not scored:
            return [next(w for w in WORKERS if w.name == "research")]
        scored.sort(key=lambda x: (x[0], x[1].name), reverse=True)
        return [worker for _, worker in scored[:limit]]

    def manifest(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        selected = [w for w in WORKERS if not names or w.name in names]
        return [{"name": w.name, "mission": w.mission, "triggers": list(w.triggers), "tools": list(w.tool_names)} for w in selected]
