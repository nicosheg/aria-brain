# Z.AI Spec for ARIA Brain

**Purpose:** a durable implementation guide for future AI coding assistants working on ARIA Brain. Read this before adding or changing a Z.ai model, API route, MCP integration, or self-hosted GLM deployment.

**Research checked:** 15 October 2026  
**Repository:** https://github.com/nicosheg/aria-brain  
**Current integration:** optional GLM-5.3 provider using ARIA's existing OpenAI-compatible provider runtime.

## 1. Executive decision

Z.ai's GLM models are useful candidates for ARIA's coding, multi-step reasoning, research synthesis and (with a separate model) multimodal document workflows. Adopt capabilities selectively; do not replace ARIA's architecture with a Z.ai-specific agent loop.

### Implemented in this change

- Registers **zai** as an optional provider in ARIA's existing provider list.
- Uses the existing AsyncOpenAI / OpenAI-compatible client; no new SDK or heavy runtime dependency is required.
- Defaults to model **glm-5.3** and general API base URL **https://api.z.ai/api/paas/v4**; both model and base URL are configurable.
- Enables reasoning explicitly and permits only Z.ai's documented **low**, **high**, and **max** reasoning-effort values. The default is **low** to avoid opting into the highest reasoning budget on every request.
- Adds environment-variable declarations to the Render Blueprint for both the web service and background worker.
- Adds provider configuration regression tests.
- Leaves the current default provider (**groq**) unchanged. GLM-5.3 is not activated in production until a Z.ai API key is supplied and ARIA is explicitly configured to prefer it.

This is provider plumbing and configuration-level test coverage—not proof of a successful live Z.ai API call. A real API key and controlled smoke test are required before making GLM-5.3 the production default.

## 2. Critical naming and licensing distinction

Do not casually describe GLM-5.3 as unrestricted “open source”.

- **GLM-5.3** is an open-weight, text-only model hosted at https://huggingface.co/zai-org/GLM-5.3. Its Hugging Face model page identifies the license as **glm-5.3**, a custom license. Before commercial self-hosting, redistribution, fine-tuning, or building a model-as-a-service product, inspect the canonical license and all conditions: https://huggingface.co/zai-org/GLM-5.3/blob/main/LICENSE
- **GLM-5.3-Flash** is a separate model, not just an alias for GLM-5.3. Its model page identifies an **MIT** license and describes native multimodal input: https://huggingface.co/zai-org/GLM-5.3-Flash
- Hosted API use is still subject to Z.ai's API terms, quotas, prices and data handling—not just the weights license. Confirm current terms and pricing in the Z.ai console before sending sensitive data or incurring meaningful spend.

GLM-5.3 is text-only per Z.ai's model guide; do not assume choosing it enables image/video understanding. Flash is the model to investigate for visual and document use cases. Sources: https://docs.z.ai/guides/llm/glm-5.3 and https://huggingface.co/zai-org/GLM-5.3-Flash

## 3. Exact provider configuration

### Environment variables

| Variable | Meaning | Default / recommendation |
|---|---|---|
| **ZAI_API_KEY** | Primary API credential | Required to use hosted Z.ai |
| **ZAI_KEY_1 … ZAI_KEY_20** | Optional additional keys following ARIA's provider-key pattern | Leave unset unless needed |
| **ZAI_MODEL** | Model identifier sent in chat-completions requests | **glm-5.3** |
| **ZAI_BASE_URL** | OpenAI-compatible API base URL | **https://api.z.ai/api/paas/v4** |
| **ZAI_REASONING_EFFORT** | GLM reasoning budget | **low**; allowed values **low**, **high**, **max** |
| **ARIA_PROVIDER** | Preferred provider across ARIA's configured providers | Keep current **groq** until Z.ai smoke tests pass; set to **zai** only if intentionally switching |

### Which endpoint should be used?

Use the general endpoint by default:

~~~text
https://api.z.ai/api/paas/v4
~~~

Z.ai also documents this endpoint for the **GLM Coding Plan**:

~~~text
https://api.z.ai/api/coding/paas/v4
~~~

The Coding Plan endpoint can be selected with **ZAI_BASE_URL**. Do not switch endpoints based only on the model name; use the endpoint that matches the account's Z.ai subscription/API product. Source: https://docs.z.ai/guides/llm/glm-5.3

### Render setup

The repository's **render.yaml** now declares **ZAI_API_KEY**, **ZAI_MODEL**, and **ZAI_REASONING_EFFORT** for both **aria-brain** (web) and **aria-agent-worker** (background worker). An existing dashboard-managed Render service may still require adding these variables in Render's Environment UI; changing a Blueprint file does not prove values are present in the live service.

1. Add **ZAI_API_KEY** to both web and worker services in Render. Never put the key in GitHub, this spec, chat, client JavaScript, or logs.
2. Set **ZAI_MODEL=glm-5.3** and **ZAI_REASONING_EFFORT=low**.
3. Leave **ZAI_BASE_URL** unset for the general endpoint unless the account uses the Coding Plan endpoint or an OpenAI-compatible self-host.
4. Keep **ARIA_PROVIDER=groq** while validating the credential and endpoint. After a successful smoke test, set **ARIA_PROVIDER=zai** in both services if GLM-5.3 should be preferred. Web and worker must use compatible provider/model settings so background runs and resumed work are not stranded.
5. Deploy and inspect startup, provider errors, one normal chat, one factual/research task, and one tool-using task before switching real users over. Do not claim these tests passed without observing actual results.

The runtime already uses configured provider order and can try other configured providers when a call fails in a retryable way. Do not add silent fallbacks that hide errors or erase provider/model identity from saved runs.

## 4. GLM-5.3 request behavior

Z.ai's current GLM-5.3 guide states that the model:
- Accepts text input (not native image/video input).
- Has a documented 1-million-token context window and maximum output of 128K tokens.
- Always has reasoning enabled; disabling reasoning is unsupported.
- Supports **reasoning_effort** values **low**, **high** and **max**.
- Supports streaming, function calling, structured output and context caching.

These are vendor-documented capabilities. Evaluate them against ARIA's actual prompts, tool schemas and budget rather than assuming vendor benchmark claims guarantee ARIA results.

OpenAI-compatible chat-completions request shape (illustrative—never include a real key in source control):

~~~json
{
  "model": "glm-5.3",
  "messages": [
    {"role": "system", "content": "ARIA's server-side instructions"},
    {"role": "user", "content": "Explain your task"}
  ],
  "thinking": {"type": "enabled"},
  "reasoning_effort": "low",
  "temperature": 1.0,
  "max_tokens": 700
}
~~~

For complex coding/reasoning, compare **high** and **max** in a controlled evaluation; do not raise the default until latency, quality and actual spend have been measured. Do not send Groq's **reasoning_effort=none** value to GLM-5.3. ARIA's fast conversation path sets GLM reasoning explicitly because GLM-5.3 does not support disabling reasoning.

Official model guide and request examples: https://docs.z.ai/guides/llm/glm-5.3  
API introduction: https://docs.z.ai/api-reference/introduction

## 5. Where GLM can help ARIA

### Use now: optional model provider, not a new architecture

ARIA already has a model-independent control plane, provider candidate list, specialist selection, common research tools, memory, controlled browser automation, MCP connections and approval gates. The Z.ai provider should plug into these paths rather than replicate them.

Best near-term evaluation tasks:
- Long, multi-step code changes and test/debug loops using the existing **developer** specialist.
- Review of ARIA architecture, API contracts, and deployment plans.
- Research synthesis where existing tools gather sources and open direct pages, while ARIA still verifies and cites the opened evidence.
- Structured extraction/planning in a future validated-schema path after compatibility tests.

Current implementation uses one selected provider/model for the ARIA run and the specialists it creates. **Per-worker multi-model routing is not implemented by this provider change.** Add it later only if measured benefits justify the extra reliability and debugging complexity.

### Next: benchmark before assigning production workload

Create a small evaluation set from real ARIA tasks, not model demos. Include:
1. factual question → direct source opening and accurate citations;
2. code bug → minimal diff, regression tests and no unrelated rewrite;
3. connected-app query → correct tool discovery and read-only access;
4. external side effect → pause for approval when required;
5. provider timeout/401/429 → safe fallback without duplicate external actions;
6. long conversation → relevant memory without dumping the full transcript;
7. Nigerian user context → useful, natural answer, with external claims properly sourced.

Record pass/fail, latency, tokens or spend when available, tool calls, source quality, regressions, and human rating. Compare against the current default provider on the same prompts. Never compare only cherry-picked examples.

### Later: GLM-5.3-Flash for multimodal workflows

Potential candidates include:
- image/document interpretation and extracting information from screenshots;
- scanned receipts, forms or image-based documents;
- visual browser assistance where a page screenshot adds information that the DOM does not expose;
- video/file inputs when an official API/runtime path is verified.

Do not switch current text requests to Flash blindly. ARIA's request schema, file transport, safe size limits, retention/privacy expectations, prompt-injection handling and output validation must be tested. Make this a separate model capability with explicit modality support and an evaluation suite. Model card: https://huggingface.co/zai-org/GLM-5.3-Flash

### Later: structured output and cache efficiency

- **Structured outputs:** use for internal plans, normalized research findings, and extraction schemas only where the model/API supports the requested schema. Validate every response locally and preserve a plain-text fallback for user-facing turns.
- **Context caching:** evaluate on repeated large stable prefixes (for example, shared instructions or an authorized codebase summary). Confirm the provider's actual cache controls, cache pricing and retention rules first. Do not add cache complexity before observing a cost/latency benefit.
- **Streaming:** add only if the frontend and API contract can propagate tokens safely without breaking saved runs, cancellation, or approval pauses. Existing non-streaming requests should continue to work.
- **Long context:** use for bounded codebase/research work when it helps. A large advertised context window is not a reason to send all memory and every conversation turn on every request. Continue selecting relevant durable memory and compacting long tasks.

### Later: controlled MCP integration

Z.ai describes server-side MCP calling in its API: https://docs.z.ai/guides/capabilities/mcp-call

**Do not enable model-provider-managed MCP calls for ARIA by default.** ARIA already has an MCP connector and approval/security policy. Direct model-to-MCP integration could create a second tool-execution path and weaken ARIA's unified approval, auditing, and external-content protections if connected carelessly.

If there is a concrete use case:
1. expose only allowlisted tools and servers;
2. start read-only;
3. route any consequential action through ARIA's existing approval mechanism;
4. log the selected tool, server, arguments, result and approval decision;
5. treat all remote responses as untrusted evidence and test prompt-injection cases;
6. prove the vendor-managed tool path cannot bypass authorization, SSRF controls, or audit records before enabling it.

## 6. Self-hosting: not on the current Render service

GLM open weights may offer deployment control and predictable marginal inference costs when suitable GPU infrastructure is available. That is a future infrastructure decision, not a reason to install model-serving software into ARIA's current small Render web/worker processes.

Potential later path:
- provision a dedicated GPU host;
- evaluate the exact upstream model, hardware memory, quantization and supported inference engine;
- serve a private OpenAI-compatible endpoint with vLLM/SGLang or another supported runtime;
- set **ZAI_BASE_URL** to the private endpoint and **ZAI_MODEL** to the server's actual model ID;
- secure the endpoint with authentication and network controls; test capacity, warmup, timeouts and model updates;
- review the specific model license (GLM-5.3 and Flash have different terms).

Official GLM-5.3 model card includes Transformers and serving entry points: https://huggingface.co/zai-org/GLM-5.3  
Flash model card includes multimodal Transformers usage and serving links: https://huggingface.co/zai-org/GLM-5.3-Flash

Do not download hundreds of gigabytes of weights or add vLLM, SGLang, GPU dependencies, or a new paid host without a separate capacity/cost decision.

## 7. Guardrails future agents must preserve

- Keep the existing ARIA runtime as orchestrator; do not replace the app with a bare GLM chatbot.
- Keep ARIA's tool authorization, approval state, encrypted credentials, SSRF restrictions, and audit trail.
- Keep factual work on ARIA's source-backed research path. A model's internal knowledge, provider search snippets, or reasoning trace is not a source citation.
- Never trust model output as validated JSON, code, URLs, recipient addresses or action arguments without local validation.
- Do not expose API keys in client code, errors, telemetry, memory, tests, or this document. Use synthetic test credentials only.
- Preserve provider and model identity in run records; do not silently relabel results from fallbacks.
- Preserve deterministic routing and fast paths for ordinary conversation. Do not send every greeting, personal question or writing request through costly web research.
- Do not allow a provider-specific endpoint or tool path to bypass the common ARIA security policy.
- Measure before increasing reasoning effort, context size, specialist count, background concurrency or spend.
- Tests can validate provider configuration without real credentials; a live provider call needs a real Z.ai key and must be reported as untested until actually exercised.

## 8. Files changed for this integration

- **aria_agent/config.py** — model, reasoning effort and provider detection settings.
- **aria_agent/runtime.py** — provider registration, configurable OpenAI-compatible endpoint, GLM reasoning parameters in both agent and fast-chat paths.
- **render.yaml** — optional Z.ai environment declarations for web and worker services.
- **tests/test_zai_provider.py** — regression coverage for optional configuration, custom endpoints and configured-model detection.
- **README.md** — points future maintainers to this specification.

## 9. Rollout checklist for future implementation work

- [ ] Merge only after GitHub Actions tests/compilation pass and the PR diff contains no unrelated changes.
- [ ] Verify the latest Render deploy is tied to the exact merged commit and is live.
- [ ] Add the Z.ai key through Render's secret/environment interface for both web and worker; never through Git.
- [ ] Keep the current provider as default until a real GLM-5.3 smoke test succeeds.
- [ ] Test fast chat, factual research with opened-source citations, tool use, retry/fallback, a background run and approval resume where applicable.
- [ ] Compare the same evaluation prompts against the existing provider at low/high/max effort and record cost/latency.
- [ ] Deploy the preferred-provider change only after tests pass; check service logs and rollback path.
- [ ] Re-check official model docs, licensing and API pricing on the day of deployment; these can change.
