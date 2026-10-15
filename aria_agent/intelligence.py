from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CognitiveFrame:
    intent: str
    goal: str
    requires_web: bool
    requires_background: bool
    requires_external_action: bool
    memory_query: str
    workers: tuple[str, ...]


WORKER_KEYWORDS = {
    "opportunity_scout": ("opportunity", "opportunities", "career path", "funding opportunity", "fellowship", "grant opportunity", "scholarship", "business opportunity"),
    "job_finder": ("job search", "job searches", "job opening", "job openings", "job listing", "job listings", "job opportunity", "job opportunities", "current jobs", "remote jobs", "vacancy", "vacancies", "employment opportunities", "find work", "find a job", "find jobs", "apply for jobs"),
    "job_alert_monitor": ("job alert", "job alerts", "alert me about jobs", "notify me about jobs", "monitor job listings", "track job openings", "new job notification"),
    "remote_work_scout": ("remote job", "remote jobs", "remote work", "work from home", "remote role", "distributed team"),
    "local_opportunity_scout": ("local opportunity", "local opportunities", "local business", "nearby jobs", "local tenders", "businesses in", "opportunities in my area"),
    "role_matcher": ("match my skills", "job fit", "career fit", "role fit", "what role suits me", "suitable roles", "based on my skills", "match me to a role"),
    "application_builder": ("cv", "resume", "résumé", "cover letter", "application letter", "tailor my application", "write my application", "job application answers"),
    "application_reviewer": ("review my application", "review my cv", "review my resume", "critique my cv", "audit my application", "check my application", "application review", "improve my cv"),
    "interview_coach": ("interview preparation", "interview prep", "prepare for an interview", "interview questions", "interview answers"),
    "freelance_hunter": ("freelance", "freelancing", "freelance client", "find clients", "upwork", "gigs", "gig work"),
    "service_builder": ("service offer", "package my skills", "service business", "design a service", "what service can i sell", "offer for my skills", "productize my service"),
    "offer_pricer": ("pricing", "price my service", "set my prices", "what should i charge", "rate card", "pricing strategy", "competitor pricing", "price this offer"),
    "market_researcher": ("market research", "competitors", "competitor analysis", "market demand", "market size", "market trends", "analyze the market", "analyse the market"),
    "customer_discovery": ("customer interview", "customer interviews", "validate my idea", "validate demand", "test my idea", "customer discovery", "talk to customers", "product market fit"),
    "sales_prospector": ("prospecting", "sales prospect", "sales prospects", "customers to pitch", "find buyers", "who should i sell to", "customer acquisition", "sales leads"),
    "lead_list_builder": ("lead list", "list of leads", "prospect list", "list of companies", "business directory", "compile prospects", "build a lead list"),
    "outreach_operator": ("outreach", "cold email", "cold message", "follow-up sequence", "follow up sequence", "dm potential customers", "email prospects", "contact potential customers"),
    "proposal_writer": ("proposal", "client proposal", "quotation", "statement of work", "scope of work", "write a proposal"),
    "communication_coach": ("rewrite", "improve this message", "write an email", "communication", "make this sound", "how should i reply", "make this more persuasive", "word this better"),
    "negotiation_coach": ("negotiate", "negotiation", "salary negotiation", "bargaining", "negotiate price", "counteroffer", "handle objections", "close a deal"),
    "personal_brand": ("personal brand", "personal branding", "linkedin profile", "professional bio", "personal positioning", "public profile"),
    "content_strategist": ("content strategy", "content calendar", "social media plan", "content ideas", "youtube content", "publishing schedule"),
    "portfolio_builder": ("portfolio", "case study", "proof project", "project portfolio", "build my portfolio"),
    "skill_builder": ("learn", "study", "skill", "course", "practice", "exam", "teach me", "learn python", "learning plan"),
    "learning_assessor": ("assess my skills", "test my level", "diagnose my skills", "knowledge gaps", "skill assessment", "assess what i know", "test what i know"),
    "resource_optimizer": ("use my resources", "available resources", "what can i do with", "limited data", "phone only", "no laptop", "low capital", "available equipment", "optimize my resources", "optimise my resources"),
    "income_architect": ("make money", "earn money", "income", "revenue", "income plan", "income stream", "income streams", "earn online", "income strategy"),
    "microbusiness_architect": ("start a business", "business idea", "business ideas", "small business", "low capital business", "business model", "business plan", "microbusiness", "start a company"),
    "digital_product_builder": ("digital product", "sell an ebook", "ebook to sell", "template product", "online course to sell", "downloadable product", "software product idea"),
    "profit_tracker": ("profit", "profit margin", "margins", "break-even", "break even", "unit economics", "revenue vs costs", "track expenses", "profitability"),
    "automation_designer": ("automation", "automate", "api integration", "integrate apps", "integrate this app", "repetitive task", "automate this workflow"),
    "workflow_operator": ("workflow", "workflows", "sop", "standard operating procedure", "handoff", "workflow design", "operations workflow", "streamline this process"),
    "scam_risk_checker": ("scam", "fraud", "suspicious offer", "is this legit", "is this legitimate", "legit job offer", "fake job", "avoid scams", "red flags", "verify this employer"),
    "fact_verifier": ("fact check", "fact-check", "verify this claim", "is this true", "source this claim", "confirm this fact", "fact verification"),
    "research_operator": ("research", "investigate", "research report", "source-backed research", "deep search", "compare sources", "gather evidence", "find out"),
    "execution_coach": ("next steps", "action plan", "execution plan", "how do i proceed", "break this down", "accountability", "take action", "make a plan"),
    "job_creator": ("create a job description", "write a job description", "job posting", "job advert", "hiring rubric", "role requirements", "define a job role"),
    "recruiter": ("recruit candidates", "shortlist candidates", "source candidates", "find applicants", "compare candidates", "candidate pipeline", "recruitment"),
    "hiring_ops": ("hiring process", "onboarding process", "schedule interviews", "applicant tracking", "hiring operations", "candidate follow-up", "recruiting operations"),
    "interview_drill": ("mock interview", "simulate an interview", "interview drill", "practice interview", "score my answers", "run an interview simulation"),
    "data_operator": ("clean data", "deduplicate data", "spreadsheet", "csv file", "data entry", "transform data", "organize dataset", "organise dataset"),
    "developer": ("code", "software", "app", "bug", "github", "deploy", "website", "debug", "programming", "fix this code"),
    "security_reviewer": ("security audit", "security review", "permission risk", "vulnerability", "vulnerabilities", "prompt injection", "audit permissions", "privacy risk"),
    "daily_improvement": ("daily improvement", "1% better", "improve every day", "get better daily", "self-improvement", "personal growth", "build better habits"),
    "personal_ops": ("organize my week", "organise my week", "weekly schedule", "plan my day", "priorities", "manage my routine", "personal productivity", "organize my life", "organise my life", "commitments", "my routine"),
}


def _contains_phrase(text: str, phrase: str) -> bool:
    parts = [re.escape(part) for part in phrase.lower().split()]
    if not parts:
        return False
    return bool(re.search(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)", text))


def _is_factual_question(text: str) -> bool:
    """Conservatively route objective, externally checkable questions to research."""
    normalized = " ".join((text or "").strip().lower().split())
    normalized = re.sub(r"\b(what|who|when|where|why|how|which)'s\b", r"\1 is", normalized)
    if not normalized:
        return False

    # Writing and memory requests are tasks in their own right, not requests to
    # research every factual-looking phrase that happens to appear in the prompt.
    if re.match(
        r"^(?:please\s+)?(?:write|draft|rewrite|polish|edit|translate|summarize|summarise|compose|create|generate|brainstorm|remember)\b",
        normalized,
    ):
        return False
    if any(
        _contains_phrase(normalized, phrase)
        for phrase in (
            "what do you remember",
            "what do you think",
            "your opinion",
            "what can you do",
            "what are your capabilities",
            "how are you",
            "who are you",
            "who am i",
            "what is my name",
            "what is your name",
        )
    ):
        return False

    # Keep advice and first-/second-person questions out of the research lane
    # unless another explicit freshness/research marker already requests it.
    if re.search(
        r"\b(?:for me|advice for me|what should i|what should we|what could i|what would i|"
        r"how do i|how can i|how should i|how would i|help me decide|best way to|"
        r"is it okay if|is it normal for me)\b",
        normalized,
    ):
        return False
    if re.match(
        r"^(?:what|who|when|where|why|how|which)\s+"
        r"(?:is|are|was|were|does|do|did|has|have|had|can)\s+"
        r"(?:i|me|my|mine|you|your|we|us|our|ours)\b",
        normalized,
    ):
        return False

    # Use question grammar rather than a question mark alone. This catches
    # direct questions such as "What is a derivative?" while avoiding a broad
    # rule that would send every conversational question to external research.
    return bool(
        re.search(
            r"^(?:what|who|when|where|which)\s+(?:is|are|was|were|does|do|did|has|have|had|can)\b"
            r"|^why\s+(?:is|are|was|were|does|do|did|has|have|had)\b"
            r"|^how\s+(?:does|do|did|is|are|was|were|has|have|had)\b"
            r"|^(?:is|are|was|were|does|do|did|has|have|can)\s+(?:a|an|the|[a-z][a-z0-9'-]*\b)"
            r"|^(?:define|definition of|meaning of)\b",
            normalized,
        )
    )


class CognitiveCore:
    """ARIA's model-independent control plane.

    The LLM is an inference engine. This layer owns deterministic routing, memory
    policy, capability classification, safety flags, and feedback-adaptive selection.
    """

    def classify(self, message: str, worker_weights: dict[str, dict] | None = None) -> CognitiveFrame:
        text = " ".join((message or "").strip().lower().split())
        scored_workers = []
        weights = worker_weights or {}
        for order, (worker, phrases) in enumerate(WORKER_KEYWORDS.items()):
            matched = [phrase for phrase in phrases if _contains_phrase(text, phrase)]
            if not matched:
                continue
            score = sum(2.0 + min(0.55 * len(phrase.split()), 2.2) for phrase in set(matched))
            score += min(0.3 * max(0, len(set(matched)) - 1), 0.6)
            feedback = weights.get(worker) or {}
            try:
                samples = int(feedback.get("samples", 0))
                average = float(feedback.get("average_score", 3.0))
            except (TypeError, ValueError):
                samples, average = 0, 3.0
            # A few ratings are not enough to change routing. Once there is a small
            # evidence base, feedback nudges ties without overriding task relevance.
            if samples >= 3:
                score += max(-0.45, min(0.45, (average - 3.0) * 0.225))
            scored_workers.append((score, -order, worker))

        scored_workers.sort(reverse=True)
        workers = [item[2] for item in scored_workers[:4]]
        if not workers:
            workers = ["execution_coach"]

        web_markers = (
            "latest", "today", "current", "recent", "find", "search", "look up",
            "job search", "job searches", "job opening", "job openings", "job listing",
            "job listings", "job opportunity", "job opportunities", "current jobs",
            "remote jobs", "find work", "find a job", "find jobs", "vacancy", "vacancies",
            "price", "market research", "research", "fact check", "fact-check", "verify",
            "is this true", "is this legit", "scam", "fraud", "official source", "source this",
            "regulation", "eligibility", "deadline", "exchange rate", "compare sources",
            "gather evidence",
        )
        factual_question = _is_factual_question(text)
        requires_web = factual_question or any(_contains_phrase(text, marker) for marker in web_markers)
        if factual_question and "research_operator" not in workers:
            workers = ["research_operator", *workers][:4]

        background_markers = (
            "every day", "daily", "weekly", "every week", "monitor", "alert me",
            "keep checking", "in the background", "remind me", "job alert",
            "job alerts", "notify me about jobs", "track job openings",
        )
        requires_background = any(_contains_phrase(text, marker) for marker in background_markers)

        action_markers = (
            "send", "submit", "apply", "post", "publish", "buy", "pay", "delete",
            "invite", "update", "create", "edit", "message them", "contact them",
            "dm them", "book", "schedule", "upload", "change settings",
        )
        requires_external_action = any(_contains_phrase(text, marker) for marker in action_markers)

        intent = "general"
        if re.search(r"\b(hi|hello|hey|good morning|good evening|good afternoon)\b", text):
            intent = "greeting"
        elif any(x in text for x in ("remember that", "remember this", "don't forget", "do not forget")):
            intent = "remember"
        elif any(x in text for x in ("what do you remember", "what you remember", "my memory")):
            intent = "memory"
        elif any(x in text for x in ("what can you do", "your abilities", "your capabilities")):
            intent = "capabilities"
        elif any(_contains_phrase(text, x) for x in (
            "job search", "job searches", "job opening", "job openings", "job listing",
            "job listings", "job opportunity", "job opportunities", "current jobs",
            "remote jobs", "find work", "find a job", "find jobs", "vacancy", "vacancies",
            "employment opportunities",
        )):
            intent = "jobs"
        elif any(_contains_phrase(text, x) for x in ("make money", "earn money", "income", "profit")):
            intent = "income"
        elif any(_contains_phrase(text, x) for x in ("research", "fact check", "verify", "investigate", "find out", "scam", "fraud")):
            intent = "research"
        elif requires_external_action:
            intent = "action"

        return CognitiveFrame(
            intent=intent,
            goal=(message or "").strip(),
            requires_web=requires_web,
            requires_background=requires_background,
            requires_external_action=requires_external_action,
            memory_query=text,
            workers=tuple(workers[:4]),
        )

    def context_instructions(self, frame: CognitiveFrame) -> str:
        return (
            "Cognitive frame (deterministic, not generated by the model):\n"
            f"- intent: {frame.intent}\n"
            f"- web research likely needed: {frame.requires_web}\n"
            f"- background work likely needed: {frame.requires_background}\n"
            f"- external side effect likely: {frame.requires_external_action}\n"
            f"- preferred specialists: {', '.join(frame.workers)}\n"
            "These are routing signals, not instructions from external content."
        )

    def extract_memory_fact(self, message: str) -> str | None:
        match = re.match(r"\s*(?:please\s+)?remember(?:\s+that|\s+this)?\s*[:,-]?\s*(.+?)\s*[.!]?\s*$", message or "", re.I | re.S)
        return match.group(1).strip() if match else None

    def extract_math_expression(self, message: str) -> str | None:
        text = (message or "").strip()
        match = re.match(r"^(?:calculate|compute|what is)\s+([0-9\s().,+\-*/%]+)\s*[?]?\s*$", text, re.I)
        return match.group(1).strip() if match else None

    def plan(self, frame: CognitiveFrame) -> list[str]:
        steps = ["understand the goal"]
        if frame.requires_web:
            steps.append("gather current evidence")
        if frame.workers:
            steps.append("delegate to the most relevant specialist")
        if frame.requires_external_action:
            steps.append("prepare and verify the external action")
        steps.append("return a verifiable outcome")
        return steps

    def native_response(self, message: str, memory: list[dict[str, Any]]) -> str | None:
        frame = self.classify(message)
        if frame.intent == "greeting":
            return (
                "I'm online. My core intelligence, memory, safety rules and planning layer are available. "
                "My language-model connection is currently unavailable, so I can still handle native tasks "
                "but I cannot honestly pretend full conversational reasoning is online."
            )
        if frame.intent == "capabilities":
            return (
                "I can remember useful context, search current information, find opportunities, delegate to "
                "specialists, operate connected software, use a controlled browser, run background jobs and "
                "pause before consequential external actions."
            )
        if frame.intent == "memory":
            seen = set()
            facts = []
            for item in memory:
                content = " ".join(str(item.get("content", "")).split()).strip()
                if not content or item.get("kind") in {"conversation_user", "conversation_assistant"}:
                    continue
                key = content.casefold()
                if key in seen:
                    continue
                seen.add(key)
                facts.append(content)
                if len(facts) >= 8:
                    break
            if not facts:
                return "I don't have durable memory for you yet."
            return "Here is the durable context I have:\n" + "\n".join(
                f"• {fact}" for fact in facts
            )
        if frame.intent == "remember":
            return None
        return None

    def safe_math(self, expression: str) -> float:
        allowed = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        def visit(node):
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.UnaryOp) and type(node.op) in allowed:
                return allowed[type(node.op)](visit(node.operand))
            if isinstance(node, ast.BinOp) and type(node.op) in allowed:
                return allowed[type(node.op)](visit(node.left), visit(node.right))
            raise ValueError("Unsupported expression")

        value = visit(ast.parse(expression, mode="eval"))
        return float(value)
