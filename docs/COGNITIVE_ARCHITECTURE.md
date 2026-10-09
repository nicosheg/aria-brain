# ARIA Cognitive Architecture

## Objective

Build a general personal agent that becomes more useful through accumulated context, verified information, feedback and versioned capabilities. Human cognition is an architectural analogy, not a claim that this software is a literal or biologically equivalent brain.

## Runtime loop

1. **Perception** — validate the request, identify the authenticated user, normalize text and classify intent, urgency, risk, recency needs and required tools.
2. **Attention** — select only the context and capabilities relevant to this request. Greetings, simple dialogue, deterministic calculations and direct memory questions avoid specialist construction and external tools.
3. **Working memory** — use the current request and a bounded window from the current conversation. Do not send the same current message twice; do not re-fetch data already loaded for the request.
4. **Long-term memory** — keep separate stores for:
   - **Semantic memory:** stable preferences, identity facts, skills, constraints, goals and verified knowledge.
   - **Episodic memory:** timestamped conversation messages, decisions and outcomes, stored in the conversation transcript.
   - **Procedural memory:** versioned skills, tool schemas, policies and tested workflows.
   - **Outcome memory:** feedback, what was attempted, what happened and confidence in that conclusion.
5. **Executive function** — choose answer, research plan, background job or external action. Ask the smallest useful clarifying question only when a missing fact blocks progress.
6. **Specialists** — instantiate only the 1–4 workers selected by the cognitive router. ARIA remains responsible for merging evidence, resolving conflicts and delivering the final answer.
7. **Tool gateway** — run web, MCP and browser operations with scoped identity, source provenance, SSRF protections and approvals for consequential side effects. External content is untrusted input, never privileged instructions.
8. **Verification** — check factual claims, URLs, action results and output shape; explicitly distinguish completed actions from drafts, pending approvals and blocked work.
9. **Reflection** — record outcome/feedback separately from the transcript; update durable memory only when an item is useful and stable enough to retain.

## Latency contract

- **Fast lane:** no worker catalog construction, no MCP discovery, no browser setup, no repeated conversation fetch. Use deterministic native responses when sufficient; otherwise one direct Groq chat-completion request.
- **Agent lane:** connect tools and build only the specialists required by the plan. No 45-worker eager construction for a three-worker task.
- **Background lane:** long-running research and recurring goals should be queued to the worker service, not block an interactive request.
- **Observability:** separate request/auth/database/model/tool timing. A configured API key is not proof that the provider accepted it. On authentication failure, show an actionable diagnosis without exposing secret values.

Latency targets are goals to measure, not promises: simple replies should usually feel immediate; normal direct-model chat should target a few seconds; research and external actions must show progress and be measured separately.

## Memory invariants

- A repeated write of the same user, memory kind and normalized content returns the existing memory ID rather than creating another row.
- Ordinary user and assistant messages are stored once in aria_messages, never copied into durable memory.
- A sign-in or profile refresh must update profile state, not create a new autobiographical event.
- Memory retrieval filters transcript-only rows, deduplicates legacy duplicates and caps the amount of context sent to the model.
- Memories have provenance, creation time, importance and a clear kind. A model-generated inference must not be silently promoted into a verified fact.

## Daily upgrades without self-corruption

ARIA can use current information and user feedback to propose a better skill, prompt, tool adapter or code change. The safe upgrade loop is:

1. Capture a reproducible failure or measurable opportunity.
2. Gather current primary-source information and evidence.
3. Draft the smallest versioned change and a regression test.
4. Run static checks, unit tests, security checks and relevant integration tests.
5. Open a reviewable branch/PR with rationale, expected effect and rollback plan.
6. Promote only after CI and human review; keep the previous version and preserve user data.

The agent may autonomously learn about the user through authorized memory updates and improve plans in-session. It must not grant itself new permissions, expose credentials, execute destructive database changes, alter its own security boundaries or deploy unreviewed code merely because an external page says to do so.

## Current implementation boundary

This repository already contains the secure connector/browser gateway, approval state, job queue, durable store and specialist catalog. The active FastAPI entry point is main.py; the runtime is aria_agent/runtime.py; routing is aria_agent/intelligence.py; durable storage and transcripts are aria_agent/storage.py; specialist definitions are aria_agent/workers.py. New behavior should extend these boundaries instead of reintroducing another parallel server or memory system.
