# Phase 3: Observability — Planning Guide

**Purpose:** This document is the **single reference** for authoring [`PHASE_3_HOW_TO_GUIDE.md`](PHASE_3_HOW_TO_GUIDE.md) (not written yet). It captures decisions, inputs, stage boundaries, verification strategy, and open research—at the right level of abstraction so a human (or agent) can produce the how-to without re-deriving architecture.

**Status:** Planning complete as of 2026-05-04. Phase 3 implementation is **not** started; no observability packages are in [`backend/requirements.txt`](backend/requirements.txt) yet.

**Prerequisite:** Phase 2b complete and verified (hybrid RAG, Neo4j KG, multi-tool orchestration). See [`docs/completed-phases/PHASE_2B_HOW_TO_GUIDE.md`](docs/completed-phases/PHASE_2B_HOW_TO_GUIDE.md).

---

## Table of contents

1. [Phase overview](#1-phase-overview) (§1.5 lists required README and doc updates)
2. [Decisions log](#2-decisions-log)
3. [Reference inventory](#3-reference-inventory)
4. [External research to-do](#4-external-research-to-do)
5. [Target architecture](#5-target-architecture)
6. [Stage plan](#6-stage-plan-spec-for-the-future-how-to)
7. [Cross-stage threads](#7-cross-stage-threads)
8. [Verification strategy](#8-verification-strategy)
9. [Open questions](#9-open-questions)
10. [Acceptance criteria for the final how-to](#10-acceptance-criteria-for-the-final-how-to)

---

## 1. Phase overview

### 1.1 Goal (from project plan)

From [`PROJECT_PLAN.md`](PROJECT_PLAN.md) § "Phase 3: Observability with Arize Phoenix":

- **Goal:** Full tracing and monitoring of agent execution.
- **Features (plan scope):** Self-hosted Phoenix on ECS Fargate (plan default), LangGraph/LangChain observability hooks, OpenTelemetry, structlog JSON for CloudWatch, trace visualization, metrics (tokens, latency, tool success, cache hit rate when cache exists, cost per request, errors by type, KG-specific metrics), CloudWatch Logs Insights and dashboards.

### 1.2 What Phase 3 will deliver in *this* repo (cost-conscious scope)

We implement **observability behavior** (traces, spans, structured metrics logs, CloudWatch queries) using **Phoenix Cloud** as the trace backend, **not** self-hosted ECS Fargate in the first pass. The project plan’s Fargate + EFS + internal ALB design remains the **documented enterprise upgrade path** (see §2 and §5.2).

### 1.3 Explicitly out of scope for Phase 3 (first pass)

- Terraform for ECS Fargate, EFS, or internal ALB for Phoenix (deferred; see stage 15 in §6).
- LangChain / LangGraph **major** version upgrades (stay on pins in [`DEVELOPMENT_REFERENCE.md`](DEVELOPMENT_REFERENCE.md)—e.g. `langgraph~=0.2.50`, `langchain~=0.3.0`).
- Replacing [`backend/src/api/middleware/logging.py`](backend/src/api/middleware/logging.py); new code **extends** it.
- Inference cache metrics until a cache exists (plan mentions cache hit rate; repo cache is Phase 4+ placeholder per [`backend/src/cache/__init__.py`](backend/src/cache/__init__.py)—how-to should say "N/A" or omit until Phase 4).

### 1.4 Estimated effort (for the future how-to author)

Rough order of magnitude: **6–12 hours** for a developer familiar with Docker and AWS, assuming Phoenix Cloud signup and one clean `terraform plan` / apply cycle for secrets + App Runner env only.

### 1.5 Documentation and repository metadata (required)

Phase 3 is not done until **repository-facing docs** reflect the new behavior, env vars, and file layout. The future [`PHASE_3_HOW_TO_GUIDE.md`](PHASE_3_HOW_TO_GUIDE.md) must include a **dedicated documentation stage** (see **Stage 20** in §6) with agent prompts or explicit human steps for each item below.

| File | Update expectation |
|------|-------------------|
| [`README.md`](README.md) | Short **Observability** subsection: Phoenix Cloud traces, OTLP export, link to `PHASE_3_HOW_TO_GUIDE.md` (once written) or this planning guide until then; mention `OBSERVABILITY_ENABLED` kill-switch; no secrets in examples |
| [`docs/README.md`](docs/README.md) | Index new docs created in Phase 3 (e.g. `docs/cloudwatch-queries.md`, observability notes); point readers to the phase how-to |
| [`REPO_STATE.md`](REPO_STATE.md) | Every new/changed path (code, Terraform, docs) per file’s “Post-creation” rules; move `PHASE_3_HOW_TO_GUIDE.md` from Planned → completed files when archived to `docs/completed-phases/` |
| [`DEVELOPMENT_REFERENCE.md`](DEVELOPMENT_REFERENCE.md) | New dependency pins and any new env vars / API surface documented in the Technology Version Reference |
| [`.env.example`](.env.example) | All new Phoenix/OTel settings with placeholder values and comments (Stage 5; listed here as a doc contract) |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Where `PHOENIX_API_KEY` lives (Secrets Manager in AWS, `.env` local only), naming pattern `enterprise-agentic-ai/...`, never commit keys, trace data leaves AWS when using Phoenix Cloud |
| [`scripts/README.md`](scripts/README.md) | Update **only if** Phase 3 adds or changes scripts used for observability verification; otherwise add one line “unchanged in Phase 3” in the how-to checklist |
| [`frontend/README.md`](frontend/README.md) | Update **only if** the frontend gains observability-related config (not planned for Phase 3); how-to should still tick “reviewed — N/A” |
| [`PROJECT_PLAN.md`](PROJECT_PLAN.md) | Optional: sync **Current status / Next steps** when Phase 3 is complete (human editorial; not a hard gate for code) |
| [`.cursor/rules/_project.mdc`](.cursor/rules/_project.mdc) | When Phase 3 implementation is complete, set **Phase** / **Guide** pointer to Phase 4 prep per project convention |

---

## 2. Decisions log

| ID | Decision | Options considered | Choice | Rationale | Cost impact |
|----|----------|-------------------|--------|-----------|-------------|
| D1 | Phoenix deployment | A) ECS Fargate + EFS + internal ALB (plan text); B) Phoenix Cloud SaaS | **B** | Portfolio demo budget target (~$20–50/mo); Fargate path is ~**$25–45/mo** extra largely from **internal ALB** (hourly, no scale-to-zero) plus Fargate task + small EFS | **~$0** marginal for Phoenix Cloud at low volume; Fargate deferred |
| D2 | Kill-switch for tracing | Always-on OTel vs env-gated | **`OBSERVABILITY_ENABLED`** (bool) + optional `PHOENIX_API_KEY` | Lets you disable export without redeploying code; supports "turn off when not demoing" | $0 |
| D3 | LangGraph / LangChain versions | Upgrade to 1.x vs stay on 0.2.x / 0.3.x | **Stay pinned** per `DEVELOPMENT_REFERENCE.md` | Avoid scope explosion; instrumentors must match tested stack | $0 |
| D4 | Logging stack | Replace structlog vs extend | **Extend** existing structlog | Already CloudWatch-oriented JSON in `aws` env; redaction processors exist | $0 |
| D5 | Where `_kg_search` lives | Unknown vs confirmed | **`backend/src/retrieval/hybrid_retriever.py`** (`HybridRetriever._kg_search`, ~line 659) | Resolved by grep; plan text `_kg_search()` refers to this implementation | — |

**Enterprise path (not implemented in Phase 3 first pass):** Deploy Phoenix per [`PROJECT_PLAN.md`](PROJECT_PLAN.md) infrastructure bullets (Fargate, EFS, internal ALB, dashboard auth). OTLP endpoint moves from Phoenix Cloud URL to internal collector URL; trace data stays in AWS account.

---

## 3. Reference inventory

Use these when writing [`PHASE_3_HOW_TO_GUIDE.md`](PHASE_3_HOW_TO_GUIDE.md). Every how-to agent prompt should cite the relevant **cursor rules** by name (pattern from prior guides).

### 3.1 Project docs

| Document | What to extract |
|----------|-----------------|
| [`PROJECT_PLAN.md`](PROJECT_PLAN.md) | Phase 3 goal, feature list, KG metric targets (§ below), infra diagram for *future* Fargate |
| [`DEVELOPMENT_REFERENCE.md`](DEVELOPMENT_REFERENCE.md) | Pinned versions for `langgraph`, `langchain`, `langchain-aws`, `structlog`, `fastapi`; **add** Phoenix/OTel/OpenInference pins after §4 research |
| [`REPO_STATE.md`](REPO_STATE.md) | Confirm paths exist before linking; add new files after each creation per update instructions at bottom of file |
| [`.env.example`](.env.example) | New vars: `OBSERVABILITY_ENABLED`, `PHOENIX_API_KEY`, `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_PROJECT_NAME`, `OTEL_SERVICE_NAME` (exact names TBD in how-to; align with Arize docs post-research) |
| [`README.md`](README.md) | Architecture or “Stack” subsection: observability (Phoenix Cloud + CloudWatch); link to phase guides |
| [`docs/README.md`](docs/README.md) | Catalog of `docs/` including Phase 3 artifacts |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Secrets and data-boundary notes for Phoenix |
| [`scripts/README.md`](scripts/README.md), [`frontend/README.md`](frontend/README.md) | Touch only if Phase 3 changes those areas (see §1.5) |

**KG metrics from plan (for span attributes or structured logs):**

| Metric | Target (plan) |
|--------|----------------|
| KG hit rate | >60% of queries where KG finds matches |
| Boost impact | Avg position change of KG-boosted chunks +2 to +3 |
| 2-hop usage | 20–40% of complex queries use 2-hop |
| KG latency | Time in `_kg_search()` <200ms |
| KG failure rate | <5% |

### 3.2 Cursor rules (cite in agent prompts)

| Rule file | Use when |
|-----------|----------|
| [`.cursor/rules/howtoguide.mdc`](.cursor/rules/howtoguide.mdc) | Structure of `PHASE_3_HOW_TO_GUIDE.md`, agent prompt formats (Python/Terraform/Config/Update) |
| [`.cursor/rules/docs.mdc`](.cursor/rules/docs.mdc) | Doc standards; `DEVELOPMENT_REFERENCE` / `REPO_STATE` update order |
| [`.cursor/rules/backend.mdc`](.cursor/rules/backend.mdc) | FastAPI, typing, pytest, error messages |
| [`.cursor/rules/agent.mdc`](.cursor/rules/agent.mdc) | LangGraph compile, `astream`, tools, state |
| [`.cursor/rules/infrastructure.mdc`](.cursor/rules/infrastructure.mdc) | Terraform modules, `terraform plan` safety |
| [`.cursor/rules/aws.mdc`](.cursor/rules/aws.mdc) | `us-east-1`, Secrets Manager naming `enterprise-agentic-ai/...` |
| [`.cursor/rules/_workflow.mdc`](.cursor/rules/_workflow.mdc) | Docker-first verification |
| [`.cursor/rules/_security.mdc`](.cursor/rules/_security.mdc) | No secrets in logs; API keys redacted; user-safe errors |
| [`.cursor/rules/_project.mdc`](.cursor/rules/_project.mdc) | Sources of truth; after phase completion update phase pointer |

### 3.3 Prior how-to guides (tone and structure)

| Guide | Use for |
|-------|---------|
| [`docs/completed-phases/PHASE_2B_HOW_TO_GUIDE.md`](docs/completed-phases/PHASE_2B_HOW_TO_GUIDE.md) | Section numbering, "What we're doing / Why this matters", agent prompt blocks, checklists |
| [`docs/completed-phases/PHASE_1B_HOW_TO_GUIDE.md`](docs/completed-phases/PHASE_1B_HOW_TO_GUIDE.md) | Terraform + Secrets + App Runner patterns, staged apply |

### 3.4 Code files to extend (confirmed paths)

| Path | Role for Phase 3 |
|------|------------------|
| [`backend/src/api/main.py`](backend/src/api/main.py) | `lifespan`: `configure_logging` → `validate_config` → **`configure_observability(settings)`** (once, sync) → **`async with get_checkpointer`** → `build_graph(checkpointer)` → `yield`. Observability init stays **outside** the checkpointer context (Stage 7 note; §9 item 1 resolved). |
| [`backend/src/agent/graph.py`](backend/src/agent/graph.py) | `build_graph()`, `get_registered_tools()`—callbacks or auto-instrumentation must attach to compiled graph / LLM clients as per chosen SDK |
| [`backend/src/agent/nodes/tools.py`](backend/src/agent/nodes/tools.py) | Tool execution node—span attributes for tool name, latency, success |
| [`backend/src/agent/tools/*.py`](backend/src/agent/tools/) | Per-tool boundaries if spans need finer granularity |
| [`backend/src/retrieval/hybrid_retriever.py`](backend/src/retrieval/hybrid_retriever.py) | `HybridRetriever._kg_search` (~659+) and hybrid pipeline—KG metric attributes |
| [`backend/src/api/middleware/logging.py`](backend/src/api/middleware/logging.py) | Existing structlog + redaction—add metrics middleware or shared helpers here or adjacent module |
| [`backend/src/config/settings.py`](backend/src/config/settings.py) | New settings fields + validation |
| [`terraform/modules/secrets/main.tf`](terraform/modules/secrets/main.tf) | Add `data` for `phoenix-api-key` secret + document manual secret creation (module references secrets, does not create them—see comments in file) |
| [`terraform/modules/app-runner/main.tf`](terraform/modules/app-runner/main.tf) | `runtime_environment_secrets` / vars for Phoenix (pattern `ARN:jsonKey::`) |

### 3.5 Knowledge graph metric implementation note

`_kg_search` is implemented on **`HybridRetriever`** in [`backend/src/retrieval/hybrid_retriever.py`](backend/src/retrieval/hybrid_retriever.py), not under `backend/src/agent/`. The how-to’s prompts must name this path explicitly to avoid agents editing the wrong file.

---

## 4. External research to-do

**Blocking for how-to authoring:** resolve each item and paste conclusions (version numbers, URLs, env var names) into a short "Research results" subsection inside the how-to or in an appendix—so prompts never contain `TODO`.

| # | Question | Where to look | What to record back |
|---|----------|---------------|---------------------|
| R1 | Compatible versions of `arize-phoenix-otel`, `openinference-instrumentation-langchain`, optional `openinference-instrumentation-bedrock`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http` with **langchain 0.3.x / langgraph 0.2.x / langchain-aws 0.2.x** | PyPI release notes + [Arize Phoenix tracing setup](https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel) | Exact `~=` pins for `requirements.txt` and `DEVELOPMENT_REFERENCE.md` |
| R2 | Phoenix Cloud OTLP endpoint shape and auth | Phoenix Cloud UI → Settings; [FAQ "What is my Phoenix endpoint?"](https://arize.com/docs/phoenix/resources/frequently-asked-questions/what-is-my-phoenix-endpoint) | Full `PHOENIX_COLLECTOR_ENDPOINT` example (may be space-specific path under `app.phoenix.arize.com`); header or env for `PHOENIX_API_KEY` |
| R3 | Does `LangChainInstrumentor` alone capture Bedrock calls made through `langchain-aws` chat models? | OpenInference docs for LangChain + Bedrock instrumentors; [openinference#1103](https://github.com/Arize-ai/openinference/issues/1103) | **§4.1:** LangChain-only for chat; do not stack Bedrock instrumentor; embeddings path separate |
| R4 | Phoenix Cloud free tier limits (trace volume, retention) as of authoring date | Arize pricing / Phoenix Cloud docs | Whether sampling is recommended for demo safety |
| R5 | CloudWatch: first N dashboards free? | Current AWS CloudWatch pricing page | Callout in how-to cost section (avoid surprise dashboard charges) |
| R6 | `register()` API for `arize-phoenix-otel` (arguments: `project_name`, `batch`, `endpoint`, etc.) | [arize-phoenix-otel SDK reference](https://arize.com/docs/phoenix/sdk-api-reference/python/arize-phoenix-otel) | Exact Python snippet for `configure_observability(settings)` |

### 4.1 R3 result — LangChain vs Bedrock instrumentors (duplicate spans)

**Conclusion for how-to / `configure_observability`:** Use **only** OpenInference **`LangChainInstrumentor`** as the default auto-instrumentor for the agent (LangGraph + `langchain-aws` **`ChatBedrockConverse`** invoke/stream paths). **Do not** also enable **`openinference-instrumentation-bedrock`** or broad **OTel AWS SDK / `bedrock-runtime` auto-instrumentation** for the same process: those hook the same underlying boto calls and, combined with LangChain instrumentation, tend to produce **duplicate or poorly nested spans** (multiple auto-instrumentors—see [Arize-ai/openinference#1103](https://github.com/Arize-ai/openinference/issues/1103) and related discussion in [Arize-ai/openinference#1632](https://github.com/Arize-ai/openinference/issues/1632)).

**Embeddings gap:** Query vectors use **`BedrockEmbeddings`** in [`backend/src/utils/embeddings.py`](backend/src/utils/embeddings.py) (boto3-first, not a LangChain `Embeddings` runnable on that path). `LangChainInstrumentor` alone may **not** emit LLM-style spans for those calls (upstream has similar gaps for embeddings—e.g. [Arize-ai/openinference#2156](https://github.com/Arize-ai/openinference/issues/2156)). If Phase 3 needs embedding visibility, add **targeted manual spans** (or a narrowly scoped helper) around `embed_text` / `embed_batch`—**not** a second global Bedrock instrumentor that would re-wrap chat.

**R1** still pins compatible package versions; this subsection answers the “both or one?” question for authoring.

**§9 tracking:** Implementation for §9 item **2** must match this subsection; when updating §9 after merge, use the strikethrough checklist in **§9.1**.

### 4.2 §9 item 3 — Token metrics source of truth (chat / Bedrock streaming)

**What the repo does today:** [`chat_node`](backend/src/agent/nodes/chat.py) streams via `ChatBedrockConverse.astream`, accumulates `AIMessageChunk` with `+`, and builds an [`AIMessage`](https://python.langchain.com/docs/concepts/messages/) with `response_metadata` copied from the combined chunk. It does **not** read or propagate [`usage_metadata`](https://python.langchain.com/docs/concepts/messages/#aimessage) (input/output token fields LangChain uses on some providers).

**Bedrock Converse streaming:** Token counts (when available) are typically delivered in **terminal** stream events (`messageStop` / metadata), not per text delta. Whether `langchain-aws` maps that onto the final chunk’s `usage_metadata` or `response_metadata` **depends on package version**—must be **verified** against pinned `langchain-aws` in [`DEVELOPMENT_REFERENCE.md`](DEVELOPMENT_REFERENCE.md) during Phase 3 (log one redacted sample trace in dev, or a short unit/integration assertion).

**Upstream caution:** Aggregated `usage_metadata` in **streaming** mode has been wrong or misleading in some LangChain versions ([langchain-ai/langchain#30429](https://github.com/langchain-ai/langchain/issues/30429)). Do not treat streamed token totals as billing-grade without validation.

**Recommended policy for the how-to (Phase 3 metrics + Phoenix attributes):**

| Priority | Metric | Source | Notes |
|----------|--------|--------|-------|
| 1 | End-to-end / node **latency** | timers in route or node | Always safe to export |
| 2 | **Stream chunks** | `_stream_response` `chunk_count` | Useful diagnostic; not tokens |
| 3a | **Tokens** (best-effort) | After stream: `usage_metadata` on accumulated chunk or final `AIMessage`, if present **and** sane (single final usage, not per-chunk multiplication) | Set span/log attribute e.g. `gen_ai.token.source=usage_metadata` |
| 3b | **Tokens** (fallback) | `response_metadata` keys from Bedrock if documented for our model | Map explicitly in code; document field names |
| 3c | **Approximate only** | Heuristic (e.g. chars/4) on prompt + completion text | Must label `approximate=true`; never use for billing |
| 4 | **Omit tokens** | If 3a–3c unavailable or untrusted | Log `token_metrics=latency_only` (or equivalent); Stage 10 still emits `latency_ms` |

**Embeddings token counts** (separate path): Titan usage in [`backend/src/utils/embeddings.py`](backend/src/utils/embeddings.py) already tracks `inputTextTokenCount` from the Bedrock response body for **embedding** calls—do not conflate with chat Converse streaming.

**§9 tracking:** §9 item **3** strikethrough checklist → **§9.2**.

---

## 5. Target architecture

### 5.1 Implemented target (Phoenix Cloud) — ASCII

```
                    ┌─────────────────────┐
                    │   Phoenix Cloud     │
                    │   (SaaS OTLP)       │
                    └──────────▲──────────┘
                               │ HTTPS + API key
                               │
┌──────────────┐     ┌──────────┴──────────┐     ┌──────────────────┐
│  CloudFront  │     │     App Runner       │     │ CloudWatch Logs │
│  + S3        │────▶│  FastAPI + LangGraph │────▶│ + Insights /     │
│  (frontend)  │     │  OTel + OpenInference│     │  Dashboards     │
└──────────────┘     └──────────┬──────────┘     └──────────────────┘
                               │
                               │ structlog JSON (existing)
                               ▼
                         (same process)
```

**Data boundary:** With Phoenix Cloud, trace payloads (including LLM/tool spans) are exported to Arize’s service. Document PII/redaction policy: rely on existing structlog redaction; avoid logging raw user messages in custom attributes; align with [_security.mdc](.cursor/rules/_security.mdc).

### 5.2 Deferred target (enterprise / plan-default) — ASCII

```
┌──────────────┐          ┌─────────────────────────────┐
│  App Runner  │──VPC────▶│ Internal ALB                │
│  (connector) │          │  → Phoenix UI (protected)   │
└──────────────┘          │  → OTLP collector           │
                          └──────────┬──────────────────┘
                                     │
                          ┌──────────▼──────────┐
                          │ ECS Fargate + EFS   │
                          │ (Phoenix self-hosted)│
                          └─────────────────────┘
```

**Cost note for how-to:** Internal ALB is a significant fixed monthly cost; EFS + Fargate add more. This path is for **data residency** or **enterprise demo**, not the default portfolio cost profile.

---

## 6. Stage plan (spec for the future how-to)

Each stage below lists **inputs**, **outputs**, **verification**, **rules to cite**, and whether a **cost compromise note** is required. The how-to guide turns each row into prose + agent prompts + exact bash commands.

---

### Stage 1 — Prerequisites verification

| Field | Content |
|-------|---------|
| **Purpose** | Confirm Phase 2b stack healthy before touching observability. |
| **Inputs** | Local `.env` or AWS secrets; Docker Compose running; optional deployed URLs from Phase 1b/2. |
| **Outputs** | None (checklist only). |
| **Verification** | `GET /health` returns OK; health payload includes Pinecone/Neo4j as today; optional `docker-compose exec backend pytest` subset. |
| **Cursor rules** | [_workflow.mdc](.cursor/rules/_workflow.mdc) |
| **Cost note** | No |

---

### Stage 2 — Architecture and cost compromise (read-through)

| Field | Content |
|-------|---------|
| **Purpose** | Align reader with §5 diagrams and §2 decisions. |
| **Inputs** | This planning doc §1–§5. |
| **Outputs** | None. |
| **Verification** | Reader acknowledgement / checklist tick. |
| **Cursor rules** | [_project.mdc](.cursor/rules/_project.mdc) |
| **Cost note** | **Yes** — Phoenix Cloud vs Fargate (short reusable paragraph; link to `PROJECT_PLAN.md` Phase 3). |

---

### Stage 3 — Phoenix Cloud account setup (human)

| Field | Content |
|-------|---------|
| **Purpose** | Obtain API key and collector endpoint for space/project. |
| **Inputs** | Arize Phoenix Cloud signup; browser. |
| **Outputs** | Values stored in local `.env` only (never commit). |
| **Verification** | Phoenix UI shows an empty project; Settings shows API key and endpoint pattern. |
| **Cursor rules** | [_security.mdc](.cursor/rules/_security.mdc) |
| **Cost note** | Yes (free tier limits—after R4). |

---

### Stage 4 — Backend dependencies

| Field | Content |
|-------|---------|
| **Purpose** | Add OTel + Phoenix + OpenInference packages. |
| **Inputs** | §4 research results R1. |
| **Outputs** | **Modify** [`backend/requirements.txt`](backend/requirements.txt); **Modify** [`DEVELOPMENT_REFERENCE.md`](DEVELOPMENT_REFERENCE.md) Technology Version Reference. |
| **Verification** | `docker-compose build backend` then `docker-compose exec backend pip check`; import smoke test for `phoenix.otel` / `register`. |
| **Cursor rules** | [docs.mdc](.cursor/rules/docs.mdc), [backend.mdc](.cursor/rules/backend.mdc) |
| **Cost note** | No |
| **Post-creation** | Update [`REPO_STATE.md`](REPO_STATE.md) if any new top-level doc paths—usually not for this stage. |

---

### Stage 5 — Settings and environment template

| Field | Content |
|-------|---------|
| **Purpose** | Typed settings + `.env.example` for all Phoenix/OTel flags and kill-switch. |
| **Inputs** | R2, R6; naming convention from existing [`backend/src/config/settings.py`](backend/src/config/settings.py). |
| **Outputs** | **Modify** `settings.py`, [`.env.example`](.env.example); optional `validate_config` / startup log line for observability mode. |
| **Verification** | App starts with `OBSERVABILITY_ENABLED=false` without API key; unit test or manual import `get_settings()`. |
| **Cursor rules** | [backend.mdc](.cursor/rules/backend.mdc), [_security.mdc](.cursor/rules/_security.mdc) |
| **Cost note** | No |

---

### Stage 6 — Observability module (`configure_observability`)

| Field | Content |
|-------|---------|
| **Purpose** | Centralize `register()` + instrumentors; no-op when disabled. |
| **Inputs** | R6; D2. |
| **Outputs** | **New** `backend/src/observability/__init__.py`, `backend/src/observability/tracing.py` (names may be adjusted in how-to but keep a single entrypoint). |
| **Verification** | Log line `observability_configured` with `enabled=true/false`; no exception on import. |
| **Cursor rules** | [backend.mdc](.cursor/rules/backend.mdc) |
| **Cost note** | No |
| **Post-creation** | [`REPO_STATE.md`](REPO_STATE.md) new files |

**§9 tracking:** §9 item **2** strikethrough criteria → **§9.1** table (instrumentor-only default + docstring).

---

### Stage 7 — Lifespan wiring

| Field | Content |
|-------|---------|
| **Purpose** | Call `configure_observability(settings)` at correct point in startup. |
| **Inputs** | Current [`backend/src/api/main.py`](backend/src/api/main.py) lifespan; outcome of R3 (instrumentor order). |
| **Outputs** | **Modify** `main.py`. |
| **Verification** | With enabled + valid key: one chat request creates a trace in Phoenix UI; with disabled: no new traces. |
| **Cursor rules** | [backend.mdc](.cursor/rules/backend.mdc), [agent.mdc](.cursor/rules/agent.mdc) |
| **Cost note** | No |

**Implementation note (resolved):** Call **`configure_observability(settings)` once** after `configure_logging` and successful `validate_config`, **before** `async with get_checkpointer(...)`. It must still run **before** `build_graph(checkpointer)` so OpenInference / OTel instrumentors attach before LLM and tool clients are used. The checkpointer context only manages the checkpoint **Postgres pool** (`AsyncPostgresSaver`); Phoenix `register()` and `TracerProvider` are process-global and do **not** need to nest inside that `async with`—nesting would incorrectly couple telemetry startup to pool acquisition and delay or skip tracing on checkpoint failures. Per-request middleware is unrelated unless the how-to adds ASGI middleware that explicitly needs the graph on `app.state` (then add **after** the block sets `app.state.graph`, not inside OTel `register()`).

**§9 tracking:** §9 item **1** strikethrough criteria → **§9.1** table (after `main.py` + G1).

---

### Stage 8 — Tool execution spans / attributes

| Field | Content |
|-------|---------|
| **Purpose** | Tool success rate, latency, error type in traces (plan metrics). |
| **Inputs** | [`backend/src/agent/nodes/tools.py`](backend/src/agent/nodes/tools.py); OTel `get_current_span()` API. |
| **Outputs** | **Modify** tool node and optionally individual tools. |
| **Verification** | Phoenix span for `sql_query` (or any tool) shows attributes; forced tool error shows `error_type`. |
| **Cursor rules** | [agent.mdc](.cursor/rules/agent.mdc), [backend.mdc](.cursor/rules/backend.mdc) |
| **Cost note** | No |

---

### Stage 9 — Hybrid retriever / KG metrics

| Field | Content |
|-------|---------|
| **Purpose** | Emit plan §3.1 KG metrics on retrieval path. |
| **Inputs** | [`backend/src/retrieval/hybrid_retriever.py`](backend/src/retrieval/hybrid_retriever.py) `_kg_search`; callers logging `kg_search_failed`. |
| **Outputs** | **Modify** `hybrid_retriever.py` (attributes or structured span events). |
| **Verification** | Single RAG-heavy query; Phoenix or logs show `kg.hit`, latency, 2-hop flag, etc. |
| **Cursor rules** | [backend.mdc](.cursor/rules/backend.mdc) |
| **Cost note** | No |

---

### Stage 10 — Request-level metrics (structlog)

| Field | Content |
|-------|---------|
| **Purpose** | Token usage and latency breakdown per HTTP request where plan requires it and Bedrock exposes usage metadata. |
| **Inputs** | Chat route [`backend/src/api/routes/v1/chat.py`](backend/src/api/routes/v1/chat.py) (and legacy [`chat.py`](backend/src/api/routes/chat.py) if still used); existing `bind_conversation_context` / `clear_context` in logging middleware. |
| **Outputs** | **New or modify** middleware (e.g. `backend/src/api/middleware/metrics.py`) + register in app factory; possibly small hooks in chat streaming to log aggregate tokens. |
| **Verification** | Log line per request with `latency_ms`, status, optional `tokens_in`/`tokens_out`; CloudWatch query in next stage returns rows. |
| **Cursor rules** | [backend.mdc](.cursor/rules/backend.mdc), [_security.mdc](.cursor/rules/_security.mdc) |
| **Cost note** | No |

**§9 / metrics:** Token semantics and fallbacks for chat streaming → **§4.2**; §9 item **3** strikethrough checklist → **§9.2**.

---

### Stage 11 — CloudWatch Logs Insights + dashboard (human + doc)

| Field | Content |
|-------|---------|
| **Purpose** | Plan deliverable: Insights queries + dashboard for key metrics. |
| **Inputs** | JSON log field names from stage 10; existing examples in [`logging.py`](backend/src/api/middleware/logging.py) docstring. |
| **Outputs** | **New** `docs/cloudwatch-queries.md` (or name per how-to) with copy-paste queries; AWS Console steps for **one** dashboard (per R5 pricing). |
| **Verification** | Each query returns ≥0 rows after test traffic; dashboard renders widgets. |
| **Cursor rules** | [docs.mdc](.cursor/rules/docs.mdc) |
| **Cost note** | **Yes** — dashboard/widget pricing warning. |

---

### Stage 12 — Secrets Manager + Terraform (API key only)

| Field | Content |
|-------|---------|
| **Purpose** | Store `PHOENIX_API_KEY` in Secrets Manager; pass to App Runner as secret env (ARN:jsonKey::). |
| **Inputs** | Manual secret `enterprise-agentic-ai/phoenix-api-key` (or agreed name—**must match** [`aws.mdc`](.cursor/rules/aws.mdc) naming); [`terraform/modules/secrets/main.tf`](terraform/modules/secrets/main.tf) pattern (data sources per secret); [`terraform/modules/app-runner/main.tf`](terraform/modules/app-runner/main.tf) env blocks. |
| **Outputs** | **Modify** secrets module (data source + document in header comment); **modify** app-runner module variables + service env. |
| **Verification** | `terraform plan` shows only additions/in-place updates; **no** unwanted App Runner replacement; `aws apprunner describe-service` shows new secret ref. |
| **Cursor rules** | [infrastructure.mdc](.cursor/rules/infrastructure.mdc), [aws.mdc](.cursor/rules/aws.mdc) |
| **Cost note** | **Yes** — Secrets Manager ~$0.40/secret/month (approximate; refresh from AWS pricing when writing how-to). |

---

### Stage 13 — Deploy to AWS

| Field | Content |
|-------|---------|
| **Purpose** | Apply Terraform; redeploy App Runner image if needed; enable `OBSERVABILITY_ENABLED` in prod after smoke. |
| **Inputs** | CI/CD from [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) or manual `terraform apply`; ECR image. |
| **Outputs** | Running service with new env. |
| **Verification** | Production `/health` OK; production chat produces Phoenix trace when enabled. |
| **Cursor rules** | [_workflow.mdc](.cursor/rules/_workflow.mdc), [infrastructure.mdc](.cursor/rules/infrastructure.mdc) |
| **Cost note** | Yes (optional note on App Runner always-on cost unchanged). |

---

### Stage 14 — End-to-end verification + kill-switch

| Field | Content |
|-------|---------|
| **Purpose** | Multi-tool conversation; confirm traces + logs + dashboard; **disable** `OBSERVABILITY_ENABLED` and confirm app still works and traces stop. |
| **Inputs** | Stages 1–13 complete. |
| **Outputs** | None (checklist). |
| **Verification** | Scripted or manual test matrix documented in how-to. |
| **Cursor rules** | [_workflow.mdc](.cursor/rules/_workflow.mdc), [_security.mdc](.cursor/rules/_security.mdc) |
| **Cost note** | Optional |

---

### Stage 15 — Optional: self-hosted Phoenix (Fargate) — documentation only

| Field | Content |
|-------|---------|
| **Purpose** | Capture enterprise upgrade path without implementing Terraform. |
| **Inputs** | [`PROJECT_PLAN.md`](PROJECT_PLAN.md) Phase 3 infrastructure bullets; §5.2 here. |
| **Outputs** | How-to section prose + bullet list of future resources (`terraform/modules/observability/`). |
| **Verification** | N/A (no apply). |
| **Cursor rules** | [infrastructure.mdc](.cursor/rules/infrastructure.mdc) |
| **Cost note** | **Yes** — full Fargate+ALB+EFS cost framing. |

---

### Stage 16 — Phase completion checklist

| Field | Content |
|-------|---------|
| **Purpose** | Single page sign-off for Phase 3. |
| **Inputs** | All prior stages. |
| **Outputs** | How-to final checklist section. |
| **Verification** | All boxes ticked. |
| **Cursor rules** | [howtoguide.mdc](.cursor/rules/howtoguide.mdc) |
| **Cost note** | Summarize |

---

### Stage 17 — Common issues

| Field | Content |
|-------|---------|
| **Purpose** | Troubleshooting table (symptom / cause / fix). |
| **Inputs** | Expected failures: wrong OTLP endpoint, missing API key, instrumentor version mismatch, Terraform secret ARN format, App Runner replacement risk. |
| **Outputs** | How-to section. |
| **Verification** | N/A |
| **Cursor rules** | — |
| **Cost note** | No |

---

### Stage 18 — Files created/modified inventory

| Field | Content |
|-------|---------|
| **Purpose** | Tables for PR / audit. |
| **Inputs** | Git diff reality after implementation. |
| **Outputs** | How-to section (must match [`REPO_STATE.md`](REPO_STATE.md)). |
| **Verification** | `REPO_STATE.md` matches disk. |
| **Cursor rules** | [docs.mdc](.cursor/rules/docs.mdc) |
| **Cost note** | No |

---

### Stage 19 — Branch management and Phase 4 preview

| Field | Content |
|-------|---------|
| **Purpose** | Git workflow; tag; **archive** completed `PHASE_3_HOW_TO_GUIDE.md` to `docs/completed-phases/`; update `_project.mdc` phase pointer to Phase 4 planning. |
| **Inputs** | Prior guides’ branch sections. |
| **Outputs** | Git commands in how-to. |
| **Verification** | Tag pushed; docs consistent. |
| **Cursor rules** | [_project.mdc](.cursor/rules/_project.mdc) |
| **Cost note** | No |

---

### Stage 20 — Documentation and repository metadata

| Field | Content |
|-------|---------|
| **Purpose** | Bring **all user-facing and maintainer-facing documentation** in line with Phase 3 reality so the repo stays navigable without reading the how-to cover to cover. |
| **Inputs** | §1.5 checklist; final git diff from Stages 4–19; completed [`PHASE_3_HOW_TO_GUIDE.md`](PHASE_3_HOW_TO_GUIDE.md) path (root or `docs/completed-phases/` after archive). |
| **Outputs** | **Modify** [`README.md`](README.md), [`docs/README.md`](docs/README.md), [`REPO_STATE.md`](REPO_STATE.md), [`DEVELOPMENT_REFERENCE.md`](DEVELOPMENT_REFERENCE.md), [`docs/SECURITY.md`](docs/SECURITY.md); **review** [`scripts/README.md`](scripts/README.md) and [`frontend/README.md`](frontend/README.md) (explicit N/A ok); **optional** [`PROJECT_PLAN.md`](PROJECT_PLAN.md) status sync; **modify** [`.cursor/rules/_project.mdc`](.cursor/rules/_project.mdc) when phase pointer should advance. |
| **Verification** | Grep for broken in-repo markdown links per [`REPO_STATE.md`](REPO_STATE.md) validation snippet; README mentions observability + kill-switch + link to canonical how-to; `REPO_STATE.md` lists every new file and removes stale “Planned” rows. |
| **Cursor rules** | [docs.mdc](.cursor/rules/docs.mdc), [_project.mdc](.cursor/rules/_project.mdc) |
| **Cost note** | No |

**Note:** Stage 20 can run **after** Stage 18 (files inventory) so the doc author copies from a frozen file list; it must still run **before** or **as part of** Stage 19 if `_project.mdc` and archive moves happen in one PR.

---

## 7. Cross-stage threads

### 7.1 Cost compromise note (boilerplate for how-to)

Reuse a short callout wherever **Cost note = Yes** in §6:

> **Cost compromise:** This phase uses **Phoenix Cloud** (low / no marginal cost at demo traffic) so traces and UI work without **ECS Fargate, EFS, or an internal ALB** (~$25–45+/mo combined, ALB billed hourly). The codebase uses standard **OpenTelemetry / OpenInference** patterns; moving to **self-hosted Phoenix** is primarily an **endpoint + deployment** change—see Stage 15. Enterprise teams choose self-hosted for **data residency** and **network isolation**.

### 7.2 Kill-switch (`OBSERVABILITY_ENABLED`)

Touch points: **Stage 5** (settings + `.env.example`), **Stage 6** (no-op path), **Stage 7** (lifespan), **Stage 12–13** (App Runner env var, default `false` until verified), **Stage 14** (prove off works).

### 7.3 `REPO_STATE.md` and `DEVELOPMENT_REFERENCE.md`

- Any **new** file → add to [`REPO_STATE.md`](REPO_STATE.md) "Currently Existing Files" per its update instructions.
- Any **new dependency** → pin in [`backend/requirements.txt`](backend/requirements.txt) **and** document in [`DEVELOPMENT_REFERENCE.md`](DEVELOPMENT_REFERENCE.md) before later stages reference versions ([docs.mdc](.cursor/rules/docs.mdc) order).

### 7.4 Agent prompt format

All executable prompts in `PHASE_3_HOW_TO_GUIDE.md` must follow [`.cursor/rules/howtoguide.mdc`](.cursor/rules/howtoguide.mdc) (Formats 1, 3, 6 for Python/config/updates; Format 2 if any Terraform **new module** is added—Phase 3 first pass only **extends** existing modules).

### 7.5 LangGraph callbacks vs auto-instrumentation

[`PROJECT_PLAN.md`](PROJECT_PLAN.md) mentions "LangGraph native callbacks (LangChainTracer)" **and** OpenTelemetry. **Resolved (R3 / §4.1):** Phase 3 default is **OpenInference `LangChainInstrumentor` only** for LangGraph + LangChain chat/tools—**no** parallel `openinference-instrumentation-bedrock` / global boto Bedrock auto-instrumentation (avoids duplicate spans on `ChatBedrockConverse`). Add explicit **LangGraph callbacks** (or manual spans) **only** where verification shows gaps—for this codebase, the main separate path is **boto-first** [`BedrockEmbeddings`](backend/src/utils/embeddings.py), not double-wrapping chat.

Document in the how-to’s Stages 6–7: one primary auto-instrumentor; kill-switch disables all registered instrumentors.

### 7.6 Documentation and repository metadata

- **Single consolidated stage:** Stage 20 executes the §1.5 checklist so README / `docs/README` / security / repo state stay aligned with code and Terraform.
- **Order:** Prefer completing Stage 18 first (inventory), then Stage 20 (docs sweep), then Stage 19 (branch, archive, `_project.mdc`)—or one PR with Stages 18–20 in sequence; the how-to must spell the chosen order.
- **No orphan docs:** Any new `docs/*.md` from Phase 3 must appear in [`docs/README.md`](docs/README.md) and [`REPO_STATE.md`](REPO_STATE.md).
- **Cross-links:** Root [`README.md`](README.md) should link to the archived how-to under `docs/completed-phases/` once moved, not to a deleted root path.

---

## 8. Verification strategy

### 8.1 Principles

- **Docker-first:** prefer `docker-compose exec backend …` per [_workflow.mdc](.cursor/rules/_workflow.mdc).
- Every implementation stage in the how-to ends with: **command**, **expected output or observable**, **if failed then …**.
- Do not leak secrets in command output examples.

### 8.2 Checkpoint tests (mandatory gates before moving on)

| Gate | After stage | Pass criterion |
|------|-------------|----------------|
| G1 | 7 | First real chat request produces a **trace** in Phoenix Cloud with LLM/tool spans |
| G2 | 12 | `terraform plan` shows **no unintended replacement** of App Runner service or IAM assets |
| G3 | 14 | Full multi-tool run + **kill-switch**: traces stop, chat still succeeds |
| G4 | 20 | **Documentation gate:** §1.5 table satisfied; `REPO_STATE.md` matches tree; no stale links to removed paths |

### 8.3 Test types by layer

| Layer | Type | Example |
|-------|------|---------|
| Dependencies | Container import / `pip check` | Stage 4 |
| Settings | Unit / startup | Stage 5 |
| Traces | Manual UI | Stages 7–9 |
| Infra | Terraform validate/plan | Stage 12 |
| Prod | curl + UI | Stage 13 |

---

## 9. Open questions

Resolve these **before** or **during** the first draft of [`PHASE_3_HOW_TO_GUIDE.md`](PHASE_3_HOW_TO_GUIDE.md).

**Strikethrough rule:** In **this** planning guide, ~~strike the item text~~ only when the answer is **implemented in this repository** (Phase 3 code + settings + verification as described in **§9.1** and **§9.2**). **Do not** strikethrough solely because the design is decided—the canonical **design** for items **1–2** already lives in **Stage 7** (item 1), **§4.1** + **§7.5** + **Stage 6** (item 2), and **§3.4**; for item **3**, the policy table lives in **§4.2**; the how-to should **reference** those sections instead of pasting long rationale.

### 9.1 Items 1–2 — planning vs implementation (what to do)

| Item | Topic | Where the settled **design** lives (no duplication needed in §9) | What **implementation** must do | When to ~~strikethrough~~ §9 below |
|------|-------|-------------------------------------------------------------------|-----------------------------------|-------------------------------------|
| 1 | Tracer lifecycle vs `get_checkpointer` | **Stage 7** implementation note; **§3.4** [`main.py`](backend/src/api/main.py) row | `configure_observability(settings)` runs **once**, **after** `configure_logging` + `validate_config`, **before** `async with get_checkpointer` → then `build_graph(checkpointer)` → `yield` | After `main.py` matches that order **and** Stage 7 **Verification** / gate **G1** has been satisfied on a real deployment or Docker stack |
| 2 | Bedrock + LangChain double spans | **§4.1**; **§7.5**; **Stage 6** (`configure_observability` registers **only** `LangChainInstrumentor` for the default path—no parallel Bedrock/boto `bedrock-runtime` auto-instrumentor) | Observability module registers **one** primary auto-instrumentor for LangChain/LangGraph chat; **module or `configure_observability` docstring** states that **`openinference-instrumentation-bedrock`** (and global Bedrock OTel on the same process) must **not** be added without revisiting §4.1; embeddings remain per §4.1 (manual spans if needed) | After that code + docstring exist **and** a smoke check (e.g. G1) shows no duplicate LLM/Bedrock span pattern |

**How-to author workflow:** Items **1–2** are **design-closed**—prompts link to Stage 6–7 and §4.1 / §7.5. Item **3** is **policy-closed**—prompts implement **§4.2**’s tiered token/latency approach and record observed behavior for pinned versions; not an open “figure out later” TODO. Items **4–5** may still need R4 / code inspection / routing audit text in the how-to until resolved or deferred.

**Maintainer workflow:** When Phase 3 implementation merges, edit §9 below: wrap the numbered line in `~~...~~` per §9.1 / §9.2, optionally add “**Implemented:**” + PR or date—keep §9.1 / §9.2 tables unchanged.

### 9.2 Item 3 — token metrics (planning vs implementation)

| Topic | Where the **planning answer** lives | What **implementation** must do | When to ~~strikethrough~~ §9 item 3 |
|-------|-------------------------------------|-----------------------------------|-------------------------------------|
| Chat streaming tokens vs latency | **§4.2** (policy table + upstream caveat) | Pick tiers **3a–3c** or **row 4** per §4.2 after **verifying** actual `usage_metadata` / `response_metadata` on accumulated chunks for pinned `langchain-aws`; wire chosen fields into Stage 10 logs and/or Phoenix span attributes with explicit `token_source` (or `latency_only`) | After code documents the chosen source in **module or settings docstring**, Stage **10 Verification** passes (`latency_ms` always; optional `tokens_in`/`tokens_out` only if source validated **or** logs explicitly omit tokens with documented reason), and a one-line note exists in the how-to or `DEVELOPMENT_REFERENCE` pointing to §4.2 |

1. **Tracer lifecycle vs async checkpointer context** — Tracked; strikethrough per §9.1 when `main.py` + G1 satisfy the row.
2. **Bedrock + LangChain double instrumentation** — Tracked; strikethrough per §9.1 when observability code + docstring satisfy the row.
3. **Token metrics source of truth** — Tracked; **planning policy §4.2**; strikethrough per §9.2 when chat metrics + Stage 10 verification match the chosen tier.
4. **Phoenix Cloud sampling** — After R4, decide if default export needs sampling for free tier safety.
5. **Legacy `/api/chat` vs `/api/v1/chat`** — Ensure metrics/tracing cover both if both remain public ([`main.py`](backend/src/api/main.py) registers both).

---

## 10. Acceptance criteria for the final how-to

[`PHASE_3_HOW_TO_GUIDE.md`](PHASE_3_HOW_TO_GUIDE.md) is complete when:

1. It follows the structure and quality bar in [`.cursor/rules/howtoguide.mdc`](.cursor/rules/howtoguide.mdc) (TOC, Quick Start, numbered sections, per-section checklists, completion checklist, common issues, files table, branch/next steps).
2. Every agent prompt uses the prescribed **Format** with **Verify** and **Post-creation** (including `REPO_STATE.md` / `DEVELOPMENT_REFERENCE.md` where applicable).
3. **Cost compromise** callouts appear wherever this planning guide marks **Cost note = Yes** (Stages 2, 3, 11, 12, 15, 16 summary).
4. **Kill-switch** is implemented and **tested in Stage 14** (`OBSERVABILITY_ENABLED=false`).
5. **§9 Open questions:** the how-to has no naked TODOs—each item is either addressed with a pointer to this planning guide (**§9.1** for items 1–2, **§9.2** + **§4.2** for item 3), **implemented** (repo + strikethrough in §9 when the maintainer updates this file), or **deferred** with owner/rationale. Items **1–3** may remain **unstruck** in §9 until code matches §9.1 / §9.2; that does not block how-to completeness if policy/design references are explicit.
6. **§4 research** is completed and versions pinned.
7. After implementation (separate from how-to authoring), [`REPO_STATE.md`](REPO_STATE.md) matches the repository; completed how-to is archived under `docs/completed-phases/` and [`_project.mdc`](.cursor/rules/_project.mdc) phase pointer updated per project convention.
8. **Stage 20 (documentation sweep)** is present in the how-to with executable steps or agent prompts for every row in **§1.5**; gate **G4** (§8.2) passes.

---

## Summary

| Artifact | Role |
|----------|------|
| **This file** (`PHASE_3_PLANNING_GUIDE.md`) | Single source of truth **before** writing the step-by-step how-to |
| **Future** `PHASE_3_HOW_TO_GUIDE.md` | Executable prompts + bash verification for humans/agents implementing Phase 3 |
| **Stage 20** | README, `docs/README`, `SECURITY`, `REPO_STATE`, `DEVELOPMENT_REFERENCE`, optional READMEs — see §1.5 |
| **Enterprise** Fargate Phoenix | Documented deferral (§2, §5.2, Stage 15)—not blocking Phase 3 Cloud path |

When this planning guide’s **§9** is empty and **§4** is filled in, you are ready to author [`PHASE_3_HOW_TO_GUIDE.md`](PHASE_3_HOW_TO_GUIDE.md).
