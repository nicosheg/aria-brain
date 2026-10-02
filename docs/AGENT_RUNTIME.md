# ARIA Agent Runtime

## What changed

ARIA is now split into a stable runtime and compatibility layer rather than one giant mutable `brain.py`.

`aria_agent/` owns model calls, public search, worker routing, connector discovery, policy, approvals, durable run state and audit events.

## Agent loop

1. Interpret the request.
2. Select specialist workers.
3. Build a bounded plan from the available tools.
4. Execute safe reads/searches.
5. Pause before external mutation in supervised mode.
6. Resume only after the user approves.
7. Verify returned tool results.
8. Report only confirmed outcomes.

The default autonomy mode is supervised. The runtime deliberately does not equate "the model decided to do it" with authorization.

## Connected apps

MCP is the first-class integration path. The connector client targets MCP `2026-07-28` stateless Streamable HTTP and falls back to the older `2025-11-25` session flow.

A connector should expose narrow, well-described native tools. ARIA discovers those tools and plans around them; it does not need a custom ARIA implementation for every SaaS product.

REST connectors are available for deterministic APIs that can be represented as an action catalog.

## Permissions

Safe read/search actions may run automatically.

Writes, sends, deletes and spending are approval-gated by default. Connector credentials are never included in the model prompt and are only decrypted inside the connector boundary.

## Workers

The worker registry includes research, job discovery and job creation, applications, income generation, microbusiness design, sales, marketing, communication, negotiation, customer success, learning, study coaching, resource optimization, personal operations, app operations, data entry, development, QA, market research, content, portfolio, finance planning, administration and review.

Workers are capability roles, not separate uncontrolled servers. The runtime is the single authority over tools and policy.

## Environment

`SUPABASE_DB_URL` enables durable Postgres state.

Any configured model key can provide the reasoning layer:

- `GROQ_KEY_1`
- `DEEPSEEK_KEY_1`
- `GEMINI_KEY_1`

Search providers are optional:

- `TAVILY_API_KEY`
- `BRAVE_SEARCH_API_KEY`
- `SERPER_API_KEY`

Connector secrets require `ARIA_CONNECTOR_ENCRYPTION_KEY`.

Set `ARIA_AUTONOMY_LEVEL=supervised` in production. Add a controlled browser/computer-use integration only after the permission, audit and isolation layers are in place.
