# Telegram → ЮСТИЦИЯ AI integration contract

PR #34 must not be merged directly into `feat/ai-council-qwen-kimi`. Both branches modify
`config.py`, `main.py`, `.env.example`, `README.md`, and dependency/runtime composition.

## Required merge order

1. Rebase/merge the AI-core branch first and retain its `Settings`, production validation,
   `CostRuntime`, storage repositories, rate limiter, and payload-bound `ApprovalExecutionService`.
2. Add Telegram settings to that expanded `Settings` model; do not replace the core model.
3. Compose the Telegram runtime and scheduler inside the core lifespan after
   `validate_runtime_security()`; pass `telegram_dry_run` explicitly.
4. Register a `telegram_publish` controlled-execution handler. Its payload must include only the
   immutable approved draft/schedule identity, destination, and content fingerprint. The handler
   invokes the existing scheduler, which rechecks live-send and allowlist at dispatch time.
5. Only after an AI editorial generator exists, call it through the core `ModelRouter` and a shared
   `CostRuntime`; it must supply a user/context identifier and honor provider privacy policy. The
   current editorial generation is deterministic and makes no model/provider call.

## Decision mapping

`DRAFT` creates no action. `APPROVE` creates an approval-required editorial draft and must become a
payload-bound Lawyer Decision before it can schedule. `AUTO` is permitted only for a low-risk
safety result, and still must pass the controlled execution handler, live-send gate, allowlist, and
delivery reconciliation. `delivery_uncertain` is terminal until an operator reconciles it; no core
retry worker may re-dispatch it.

## Conflict inventory

| Area | Core ownership | Telegram integration rule |
| --- | --- | --- |
| Settings/.env | Core cost, storage, lawyer identity | Add Telegram fields; preserve all core fields |
| Lifespan | Core runtime validation/metering | Start Telegram only after core validation |
| Approval | Payload-bound action ledger | Editorial approval is domain state, not execution authorization |
| AI | ModelRouter + CostRuntime + privacy policy | No direct editorial LLM client |
| SQLite | Telegram MVP persistence | Do not place tokens in DB; migrate to core durable storage only deliberately |

No merge is safe until a combined worktree passes the real CI suite and verifies the controlled
execution handler against the core approval ledger.
