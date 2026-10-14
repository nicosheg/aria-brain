# ARIA Brain

ARIA is a tool-using, multi-worker personal agent runtime.

## Production architecture

The live FastAPI service no longer imports the legacy monolithic brain.py request path. ARIA now runs through a dedicated agent runtime with:

- durable memory in PostgreSQL/Supabase, with a local JSON fallback for development
- resumable human approval for side-effectful tool calls
- Streamable HTTP MCP connections for external software, with legacy SSE support and per-tool approval policies
- browser automation for websites that do not expose an API/MCP server, including live page inspection, stable element references, form filling, uploads and approved submissions
- a durable background-job queue with scheduling, leases, retries, cancellation and a separate Render worker
- 45 specialist workers covering opportunity discovery, jobs, applications, freelancing, services, sales, communication, learning, research, resource use, automation, software and execution
- configurable provider selection across OpenAI and OpenAI-compatible endpoints, with run-resume pinning to the original provider/model

## Connected apps

The preferred integration contract is MCP. A connected MCP server exposes its own tools and data model; ARIA discovers the available tools at runtime instead of hard-coding one integration per app.

Create a connection through POST /connections with:
name, url, kind=mcp, token, and optional metadata.

ARIA keeps connection secrets encrypted at rest. The frontend never needs to know the bearer token again after connection. Destructive or external side-effect tools should use the approval flow.

For websites without MCP, ARIA includes a Playwright browser controller for navigation, inspection, form filling, keyboard interaction and approved submission.

## Agent workers

The current worker catalog contains 45 specialists spanning opportunity discovery, job finding, job alerts, remote/local work, role matching, application building/review, interview coaching, freelancing, service design, pricing, market research, customer discovery, sales prospecting, lead generation, outreach, proposals, communication, negotiation, personal brand, content, portfolios, skill development, resource optimization, income planning, microbusinesses, digital products, profit tracking, automation, workflow execution, scam detection, fact verification, research, execution coaching, job creation, recruiting, hiring operations, interview drills, data operations, software development, security review, daily improvement and personal operations.

These are specialists, not separate chatbots. ARIA remains the manager, combines evidence, decides what matters next and owns the final user-facing outcome.

## Security model

Normal API requests require a Firebase ID token. The old email-only identity route exists only when ARIA_ALLOW_EMAIL_IDENTITY=true for local development.

External content is treated as untrusted data. Tool actions that can change external state may pause the run for human approval. Approval snapshots are stored server-side and encrypted; clients cannot supply arbitrary serialized RunState.

## Deployment

Render deploys one web service and one background worker. The web service handles interactive requests. The worker executes queued long-running work independently of web request timeouts.

Set at least one active model credential in Render. Supported provider variables are:
- Groq: `GROQ_API_KEY` and optional `GROQ_KEY_1` through `GROQ_KEY_20`
- OpenAI: `OPENAI_API_KEY` (optional `OPENAI_MODEL`)
- DeepSeek: `DEEPSEEK_API_KEY` and optional `DEEPSEEK_KEY_1` through `DEEPSEEK_KEY_20`
- Gemini: `GEMINI_API_KEY` and optional `GEMINI_KEY_1` through `GEMINI_KEY_20`
- OpenRouter: `OPENROUTER_API_KEY` (optional `OPENROUTER_MODEL`)
- DashScope: `DASHSCOPE_API_KEY` and optional `DASHSCOPE_KEY_1` through `DASHSCOPE_KEY_20`

ARIA tries the preferred provider first, then other configured providers. A key rejected with an authentication error is skipped for the lifetime of that process; replacing a key in Render and redeploying clears that cache. Keep secrets in Render, never in chat or source control.

Also set:
`ARIA_APP_SECRET`
`ARIA_ENCRYPTION_KEY` (recommended)
`SUPABASE_DB_URL`
`FIREBASE_CREDENTIALS`
Run locally with:
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload

Then run:
pytest -q
python -m compileall -q aria_agent main.py tests

## Production boundary

For production, set `ARIA_REQUIRE_DATABASE=true` and provide `SUPABASE_DB_URL`. This keeps job claims, approval state, memory and connected-app configuration shared across Render web/worker processes. Local JSON remains a development fallback.

The agent uses explicit human approval for side-effectful browser/MCP actions. External web content is treated as untrusted input. Connection URLs are checked against public-network SSRF constraints, and stored connection secrets are encrypted.

## Current scope

ARIA is designed as a general agent runtime rather than a single-purpose NYEOCARE bot. It can research current opportunities, delegate specialist work, remember useful context, run background goals, connect to software through MCP, operate websites through a controlled browser, and pause for human approval before consequential external actions.


## Cognitive architecture and safe self-improvement

See **docs/COGNITIVE_ARCHITECTURE.md** for the canonical design. Ordinary conversation uses a lightweight direct-model lane; research, browser control, connected apps and background goals use the tool-using executive lane. Specialists are created selectively from deterministic intent signals instead of loading the entire catalog for every request.

Conversation transcripts are episodic memory. Durable memory is reserved for useful facts, preferences, goals, constraints and decisions; chat turns must never be inserted into the durable-memory table. Duplicate writes are idempotent and retrieval deduplicates legacy rows, so old repeated records cannot drown out better context.

ARIA can learn from new information and feedback by updating user memory, versioned skills, evaluations and improvement proposals. It must not silently rewrite or deploy its own production code: software changes go through a branch, tests, reviewable diff and green CI. This keeps daily upgrades fast without allowing a mistaken observation or prompt injection to alter the system.


## Evidence-first teamwork and continual improvement

Every specialist is explicitly routable through a worker keyword catalog checked against the 45-worker registry. All specialists receive the same read-only web search, job search, direct-page fetch, calculator and scoped memory search tools. Current multi-specialist requests can invoke a parallel specialist panel; the main ARIA agent owns evidence comparison and the final answer.

Search results include publisher-class hints (government/regulator, recognized institutional publisher, scholarly publisher/repository, employer-hosted job system, recognized listing platform or unverified third party). These are not truth scores. ARIA must open material direct pages, check recency and relevance, cite exact URLs, and state when it cannot verify a claim. Job-board results must be checked against the employer or an employer-hosted application page when available.

User ratings can be linked to the exact run. ARIA uses repeated single-specialist ratings (at least three) to nudge future specialist selection for that user; it does not attribute a team's aggregate rating to each worker or silently retrain foundation-model weights from arbitrary chat text. Code/prompt updates still require tests and review.

When shared Postgres is configured, the API process also starts a small embedded queue consumer by default (disable it with ARIA_EMBEDDED_WORKER=false). It cooperates with the separately declared worker using atomic queue claims. A Render free service can sleep, so embedded queue processing is not a 24/7 service-level guarantee.
