# Z.AI Source-Code Audit and Reuse Spec for ARIA Brain

**Purpose:** help a future AI coding assistant understand what is actually available in Z.ai's GLM-5.3 source ecosystem, what is reusable, what fits ARIA today, and what would be wasteful or unsafe to copy.

**Audit date:** 15 October 2026  
**ARIA repository:** https://github.com/nicosheg/aria-brain  
**Scope:** source-code research and integration decisions. **This document does not configure GLM-5.3 as an ARIA provider.**

## Executive decision

The official source is accessible, but GLM-5.3 is not a compact, ready-to-merge autonomous-agent framework. Z.ai publishes a model repository, model configuration and chat template; the model architecture implementation is available through Hugging Face Transformers and the inference runtimes it supports. The Z.ai GitHub repository also has deployment examples and a documentation-only skill catalogue.

The strongest transferable engineering idea found is GLM-5.3's careful handling of tool-call/result IDs before reordering results for model input. It validates that IDs exist, are unique, and match the assistant's tool calls, and only reorders results when that can be done safely. That pattern is worth preserving as an invariant for any future custom ARIA model-serialization layer.

**Do not duplicate that chat-template logic in the current ARIA runtime.** ARIA delegates tool execution and run-state serialization to the OpenAI Agents SDK and has server-side resumable runs, approval handling, and tests for exactly-once approval resumption. A second custom tool-call serializer would create a competing authority and a new failure surface without clear current benefit.

No GLM-5.3 model provider, inference endpoint, new API credential, heavyweight inference dependency, model weights or GPU runtime is added by the intended source-code integration work.

## 1. Upstream source map

### A. Z.ai's official GLM repository

Repository: https://github.com/zai-org/GLM-5

Audited files:
- `README.md`: model-family overview, model download links, and pointers to supported inference frameworks.
- `requirements.txt`: minimal development/model-use dependencies listed by the repo (`transformers`, `pre-commit`, `accelerate`).
- `example/ascend.md`: Ascend/NPU deployment guidance, with inference-optimization topics such as fused expert operations, communication/computation overlap, multi-token prediction, scheduling, index caching, prefill/decode separation and quantization.
- `skills/glm-master-skill/SKILL.md`: documentation-only catalogue of official skills from the GLM-OCR, GLM-Image and GLM-V projects. The file intentionally does not execute subprocesses or local scripts.

The repository is **Apache-2.0** licensed. Official license: https://github.com/zai-org/GLM-5/blob/main/LICENSE

It is useful for source navigation, model deployment examples and the skills ecosystem. It does not itself contain a replacement for ARIA's executive agent runtime.

### B. Official GLM-5.3 model files

Model: https://huggingface.co/zai-org/GLM-5.3

The current model repository contains the model card, `LICENSE`, `config.json`, `generation_config.json`, `chat_template.jinja`, and model weights. The current repository page reports about **756 GB** of weights across **141 safetensors shards**. This is not viable on ARIA's current Render web/worker service.

The model's chat template is here:
https://huggingface.co/zai-org/GLM-5.3/blob/main/chat_template.jinja

Its license is the separate custom **GLM-5.3 License**, not the Apache-2.0 license in the Z.ai GitHub source repository:
https://huggingface.co/zai-org/GLM-5.3/blob/main/LICENSE

That model license grants broad rights to use, copy, modify, merge, publish, distribute, sublicense, sell copies, deploy, fine-tune and create derivative works, subject to its conditions. It requires retaining the copyright and permission notice. It also has a special security-review condition for a Model-as-a-Service business above the stated **US$10 billion aggregate revenue over a consecutive 12-month period** threshold. Review the exact license text before redistributing model assets or launching a product affected by those conditions.

**“No license fee” is not “no license”.** Apache-2.0 requires compliance with its notices and terms. The custom GLM-5.3 license also has conditions. Preserve upstream notices if any covered code/assets are copied.

### C. Model architecture implementation

Hugging Face Transformers has model implementation files under:
https://github.com/huggingface/transformers/tree/main/src/transformers/models/glm5_next

Relevant files include `modular_glm5_next.py`, `modeling_glm5_next.py`, configuration files and multimodal processing files. These implement neural-network architecture, tokenization/processing and inference integration. Transformers is an Apache-2.0 project.

These files can be studied for model-runtime work but are **not** ARIA's agent-orchestration layer. Pulling the model implementation into ARIA would not provide GLM intelligence by itself; it would still require the actual weights, compatible inference software, extreme memory/GPU resources, and considerable deployment engineering.

## 2. What the GLM-5.3 chat template actually does

The chat template is model-input serialization code, not a general-purpose agent runtime. Relevant implementation blocks include:
- Tool schema serialization while filtering internal metadata fields such as `defer_loading` and `strict`.
- Matching tool references to declared tool schemas by name.
- Normalizing tool results into the expected model-specific observation format.
- Resolving IDs from `tool_call_id` or `id`.
- Detecting duplicate result IDs, missing IDs, IDs that do not correspond to an assistant tool call, and duplicate assistant tool-call IDs.
- Reordering tool results to the matching assistant-call order **only if validation shows that reordering is unambiguous**.
- Stopping validation loops early once an invalid condition has already been detected.

Source locations: https://huggingface.co/zai-org/GLM-5.3/blame/main/chat_template.jinja (see the helper macros and tool-message handling near lines 826–1065).

Why this matters: tool calls and results must remain paired. Sorting tool outputs by arrival order or assuming IDs are always valid can produce a misleading context. GLM's template explicitly validates before it changes ordering.

Why this should **not** be pasted into ARIA right now:
1. It emits GLM-specific token markers such as `<|assistant|>`, `<|observation|>` and `<tool_call>`; those are not OpenAI Agents SDK's internal state format.
2. ARIA invokes tools through the Agents SDK, which owns the model/tool protocol and resumable `RunState`.
3. ARIA stores approved run state server-side, encrypts it, and tests that a run cannot be resumed twice. Adding a second serializer would risk changing protocol semantics.
4. A copied Jinja template is subject to the GLM-5.3 model license and attribution conditions, not automatically the Apache license of the separate GitHub repo.

## 3. Reusable ideas ranked by ARIA benefit

### Priority 1 — preserve tool-call/result integrity (principle, not copied template)

**Candidate use:** only if ARIA later adds a custom provider-specific transcript serializer, an offline agent replay format, or a local GLM-serving adapter.

Required invariant for that future layer:
- Every tool result must have a non-empty invocation ID.
- Each result ID must match one real invocation in the immediately relevant tool-call batch.
- An invocation/result ID must not appear twice.
- Do not reorder results if any ID is missing, repeated or unmatched.
- When every ID is valid and unique, order results by the original invocation list, not network completion order.
- Keep a conservative fallback that preserves original order when validation is ambiguous.
- Test interleaved calls, batched output records, missing/duplicate IDs, unknown IDs, result-order permutations, and empty batches.

**Current status:** not implemented as a duplicate ARIA layer, because the SDK already owns tool-message serialization. Do not add this adapter unless a measured bug or a custom serialization requirement justifies it.

### Priority 2 — explicit capability/skill discovery

Z.ai's `skills/glm-master-skill/SKILL.md` uses a simple pattern: classify user intent, point to the specific official skill, open that skill's instructions before using it, and keep installation/key handling explicit. The master skill is intentionally documentation-only, not an executable installer.

ARIA already has 45 routed specialists and existing tool discovery, so duplicating the GLM catalogue inside the runtime is not useful. If ARIA later supports genuinely installable capability packs, reuse the *concept* of a small, documented registry with capability metadata, source links, prerequisites, license, safety level and verification tests—not a second static list of workers.

Adjacent official skill sources include:
- GLM-OCR (text, table, formula and handwriting extraction): https://github.com/zai-org/GLM-OCR
- GLM-V (visual/document workflows): https://github.com/zai-org/GLM-V
- GLM-Image (image generation): https://github.com/zai-org/GLM-Image

These are separate projects and may have separate models, dependencies, API keys and licenses. They are **not** GLM-5.3 code by default. Investigate each project independently before adapting anything.

### Priority 3 — long-horizon engineering evaluation

Z.ai's GLM-5 README reports that its models are aimed at longer coding/system-engineering tasks. That is a product/evaluation claim, not a standalone implementation we can import. The ARIA-ready improvement is to measure whether a proposed orchestration change genuinely helps:
- Break goals into bounded subtasks with explicit acceptance conditions.
- Store durable task progress and the last verified state separately from chat transcript.
- Run tests/checks after each code change and use evidence rather than a model's self-assessment to declare completion.
- Stop or request approval when a task requires destructive external action, new spending, secrets, or a material change in scope.
- Avoid unbounded loops and cap turns, time, concurrent specialists and spend.

ARIA already implements worker routing, scheduled/background jobs, run state, tool approvals, source evidence and user feedback. Audit these existing paths before creating another planner or agent loop.

### Priority 4 — model-specific inference optimization (not for current Render)

The Ascend deployment example discusses fused expert kernels, communication/computation overlap, multi-token prediction, load scheduling, index/prefix caching, prefill/decode separation and quantization. These are inference-server and accelerator optimizations—not improvements to ARIA's Python orchestration loop. They belong in a separate GPU-serving project if ARIA ever self-hosts a GLM model on suitable infrastructure.

Do not install Ascend, CUDA, vLLM, SGLang, or other GPU/model-serving stacks into the existing small Render processes. The official flagship model's weight size makes this particularly inappropriate for the current service.

## 4. Concrete ARIA implementation decision

Keep the existing production architecture unchanged:
- `CognitiveCore` determines intent and selects the relevant specialist set.
- `AriaRuntime` builds the Agents SDK agent and tools.
- `MCPConnectorManager` exposes the user's connected systems.
- `AgentStore` keeps memory, messages, jobs and encrypted resumable run state.
- Existing approval gates remain the only authority for consequential external actions.
- The direct-source evidence requirement continues to govern factual/research tasks.

The provider-only change proposed during the initial interpretation was not what the user asked for; it is being removed. Do not reintroduce `ZAI_API_KEY`, `ZAI_MODEL`, `ZAI_BASE_URL`, `ZAI_REASONING_EFFORT`, or an `ARIA_PROVIDER=zai` setting as part of this source-code audit.

At the end of this review, no GLM model weights or model-specific Jinja template should be copied into the active ARIA runtime. No provider integration is necessary to retain the findings here.

## 5. Reuse and license checklist for future AI coding assistants

Before importing any code from this ecosystem:
1. Confirm the exact repository, file and revision; do not assume a license applies across all projects.
2. Read that file's governing license. Distinguish the Apache-2.0 GitHub repo, the custom GLM-5.3 model license, GLM-5.3-Flash's separate license, and any third-party inference library license.
3. If copying Apache-2.0 code, include its license and retain relevant copyright/attribution/NOTICE materials; clearly mark modified files.
4. If copying from the GLM-5.3 model repo, preserve the GLM-5.3 copyright and permission notice and check its additional terms.
5. Prefer implementing the same general invariant in ARIA's own idiom when copying is unnecessary.
6. Don't copy architecture code just to say it was merged. Confirm that the code operates on the same data format and fixes a documented ARIA limitation.
7. Add regression tests for malformed, duplicate, missing and out-of-order tool results before modifying any orchestration/serialization path.
8. Run the full tests suite, then verify the same merged commit is live on Render and test the actual affected behavior.

## 6. Canonical source links

- Official GLM-5 source repository and Apache-2.0 license: https://github.com/zai-org/GLM-5
- Official GLM-5.3 model files: https://huggingface.co/zai-org/GLM-5.3/tree/main
- GLM-5.3 license: https://huggingface.co/zai-org/GLM-5.3/blob/main/LICENSE
- GLM-5.3 chat template and history: https://huggingface.co/zai-org/GLM-5.3/blob/main/chat_template.jinja
- Hugging Face Transformers GLM-5 Next model implementation: https://github.com/huggingface/transformers/tree/main/src/transformers/models/glm5_next
- Official skill catalogue: https://github.com/zai-org/GLM-5/tree/main/skills/glm-master-skill
- Official deployment example: https://github.com/zai-org/GLM-5/blob/main/example/ascend.md
