# ARIA Brain

ARIA is a tool-using, multi-worker personal agent runtime built around a single execution authority: ARIA plans, delegates, verifies and controls tools while specialist workers provide focused expertise.

## Production architecture

ARIA runs through a dedicated agent runtime with:

- durable PostgreSQL/Supabase memory, connections, runs and background jobs, plus a local JSON development fallback
- resumable human approval for side-effectful tool calls using the Agents SDK run-state mechanism
- Streamable HTTP MCP connections for external software with per-tool filters and approval policy
- guarded Playwright browser automation for websites without an API/MCP surface
- a separate Render background worker for long-running and recurring tasks with leases and retries
- 45 specialist workers covering work discovery, job creation, applications, income, business building, sales, communication, learning, research, operations, software, QA and continuous improvement
- web research fallback across configured Tavily, Brave and Serper providers plus DuckDuckGo
- dedicated job-search routing across public job and freelance sources
- provider failover across OpenAI and OpenAI-compatible endpoints

The runtime treats external pages, app responses, uploaded files and messages as untrusted data. They can supply evidence, but they cannot silently redefine ARIA's authority or approval policy.

## Connected apps

MCP is the preferred integration contract. A connected MCP server exposes its own tools and data model; ARIA discovers those tools at runtime instead of hard-coding one integration per app.

Connections keep bearer credentials encrypted at rest. Tool allow-lists and block-lists can restrict a connection. Tool names that indicate writes, messages, purchases, deletes, deployments or other consequential operations are approval-gated before execution.

For websites without MCP, ARIA includes a persistent per-user Playwright browser controller for navigation, inspection, screenshots, form filling, keyboard interaction and approved submission. Browser and web-fetch egress blocks private/local network targets to reduce SSRF risk.

## Agent workers

The worker catalog contains focused specialists for work and job discovery, job creation and hiring, role matching, applications, interviews, freelancing, gigs, service offers, microbusinesses, pricing, market research, local opportunity discovery, sales, lead generation, outreach, negotiation, customer success, personal brand, content, distribution, learning, study coaching, resource optimization, income planning, portfolio building, customer discovery, process mapping, automation, app operations, data operations, development, QA, security review, operations management, personal operations, finance planning and daily improvement.

They are specialists, not separate uncontrolled agents. Each worker produces advice and evidence through bounded tools; the main ARIA runtime owns the final plan, permissions, external side effects and verification.

## Authentication and security

Normal API requests require a Firebase ID token. Email-only identity exists only when ARIA_ALLOW_EMAIL_IDENTITY=true for local development.

Secrets are encrypted at rest. Secret-like text is redacted before durable conversation memory. Approval state is stored server-side and is not accepted from the browser as arbitrary serialized state.

Outbound HTTP fetches and MCP connections reject localhost, metadata endpoints and private/reserved IP ranges. Browser mutation tools apply explicit approval checks for consequential interactions.

## Research and model configuration

The default model can be overridden with ARIA_MODEL. The current free-first configuration can use Groq, DeepSeek or Gemini keys; an OpenAI API key enables the primary OpenAI model path.

For current web research, configure one or more of: TAVILY_API_KEY, BRAVE_SEARCH_API_KEY, SERPER_API_KEY.

Job-search tool queries use site-specific public search routes so ARIA can compare opportunities rather than depend on one listing provider.

## Deployment

Render deploys one web service and one background worker. The web service handles interactive requests; the worker executes queued long-running work independently of request timeouts.

Set: OPENAI_API_KEY or GROQ_KEY_1+, DEEPSEEK_KEY_1+, GEMINI_KEY_1+, ARIA_APP_SECRET, ARIA_ENCRYPTION_KEY, SUPABASE_DB_URL, FIREBASE_CREDENTIALS.

For production, keep ARIA_ALLOW_EMAIL_IDENTITY=false and provide a durable database and encryption key.

Run locally with: pip install -r requirements.txt; playwright install chromium; uvicorn main:app --reload

Validate with: pytest -q; python -m compileall -q aria_agent main.py tests