# ARIA Brain

ARIA Brain is the agent runtime behind ARIA: planning, specialist workers, memory, public research, connected-app tools, approvals, audit trails and verification.

## Runtime

The production entrypoint is `main.py`. The old monolithic `brain.py` is now only a compatibility facade. New capabilities belong under `aria_agent/`.

The runtime is designed around:

- a manager/orchestrator that plans the task
- specialist workers for research, jobs, income, sales, learning, communication, software and operations
- a policy layer that separates read/search actions from mutating or sensitive actions
- approval checkpoints before external sends, deletes, purchases or other configured side effects
- MCP and REST connectors so one connected application can expose its native tools to ARIA
- durable Postgres state for runs, approvals, connectors, agent memory and audit events
- model failover across configured Groq, DeepSeek and Gemini keys
- public web-search fallback for research and opportunity discovery

## Environment

Required for durable production state:

`SUPABASE_DB_URL`

LLM keys are optional because ARIA has deterministic fallbacks, but at least one is recommended:

`GROQ_KEY_1`, `DEEPSEEK_KEY_1`, or `GEMINI_KEY_1`

For search quality, optionally configure:

`TAVILY_API_KEY`, `BRAVE_SEARCH_API_KEY`, or `SERPER_API_KEY`

For encrypted connector credentials:

`ARIA_CONNECTOR_ENCRYPTION_KEY`

Autonomy defaults to `supervised`. Use `ARIA_AUTONOMY_LEVEL=supervised` in production and expand permissions only intentionally.

## Connected software

MCP is the preferred connector when an application already exposes an MCP server. REST is supported for APIs that expose a stable action catalog.

A connector is registered against one user identity. ARIA discovers the available native tools, plans against those tools, and applies its policy before executing them. The model never receives raw connector secrets.

## Local checks

```bash
python -m compileall -q .
pytest -q
uvicorn main:app --reload
```

## Safety and verification

ARIA must report only actions confirmed by tool results. External mutation is approval-gated in the default supervised mode. Each agent run and tool decision is auditable.
