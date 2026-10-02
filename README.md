# ARIA Brain

ARIA is a tool-using, multi-worker personal agent runtime.

## Production architecture

The live FastAPI service no longer imports the legacy monolithic brain.py request path. ARIA now runs through a dedicated agent runtime with:

- durable memory in PostgreSQL/Supabase, with a local JSON fallback for development
- resumable human approval for side-effectful tool calls
- Streamable HTTP MCP connections for external software
- browser automation for websites that do not expose an API/MCP server
- a durable background-job queue and a separate Render worker
- 22 specialist workers covering jobs, income, sales, communication, learning, research, resource use and execution
- provider fallback across OpenAI and OpenAI-compatible endpoints

## Connected apps

The preferred integration contract is MCP. A connected MCP server exposes its own tools and data model; ARIA discovers the available tools at runtime instead of hard-coding one integration per app.

Create a connection through POST /connections with:
name, url, kind=mcp, token, and optional metadata.

ARIA keeps connection secrets encrypted at rest. The frontend never needs to know the bearer token again after connection. Destructive or external side-effect tools should use the approval flow.

For websites without MCP, ARIA includes a Playwright browser controller for navigation, inspection, form filling, keyboard interaction and approved submission.

## Agent workers

The worker catalog currently covers:
opportunity scouting, job finding, role matching, applications, freelancing, service building, pricing, market research, prospecting, outreach, communication, personal brand, content, skill building, resource optimization, income planning, portfolio building, negotiation, customer discovery, automation design, execution coaching and daily improvement.

These are specialists, not separate chatbots: ARIA delegates to them and owns the final plan and execution.

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
