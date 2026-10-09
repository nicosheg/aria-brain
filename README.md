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

Set:
OPENAI_API_KEY or GROQ_KEY_1+, DEEPSEEK_KEY_1+ or GEMINI_KEY_1+
ARIA_APP_SECRET
ARIA_ENCRYPTION_KEY (recommended)
SUPABASE_DB_URL
FIREBASE_CREDENTIALS

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
