# Telegram Scheduler v3 deployment contract

This document pins the production migration contract for Telegram channel `@iznanka_ugolovki`.

## Live / candidate scenarios

- Current live Make scenario: `7305820` — `Telegram @iznanka_ugolovki — Production Scheduler v2 — LIVE`.
- Candidate Make scenario: `7311904` — `Telegram @iznanka_ugolovki — Production Scheduler v3 — OFF`.
- Read-only Telegram preflight: `7311962` — `TEMP — Telegram v3 Read-Only Preflight`.

The Make plan currently allows only one active scenario. v2 and v3 must therefore never be active at the same time. The read-only preflight is executed only inside the controlled cutover window after v2 is disabled and before v3 is enabled.

## v3 safety gate

A candidate can reach claim only when all applicable conditions are true:

- `Status = Ready`;
- `Platform = Telegram`;
- `Publication ID` is non-empty;
- Publish Date is due;
- Publication Type is `text`, `photo`, `poll`, or `quiz`;
- Fact Check Status is `verified`;
- Legal Risk is `low`;
- Privacy Risk is `low`;
- Current Case Risk is false;
- Delivery State is `pending`;
- Reconciliation Required is false;
- Editorial Blockers is empty;
- type-specific required payload fields are present.

The AI editor cannot set `Ready`; human approval remains mandatory.

## Delivery payload hash

`Content Fingerprint` is reserved for editorial/content deduplication.

`Delivery Payload Hash` is a separate SHA-256 that binds the exact Telegram send attempt to a Publication ID. It is calculated immediately before delivery claim using this canonical field order:

```text
chat=<chat>|type=<type>|content=<content>|caption=<caption>|photo=<photo>|question=<question>|options=<options>|correct=<correct>|explanation=<explanation>
```

The current Make SHA-256 module is module `22` in scenario `7311904`.

JAFAR reproduces the same contract in `telegram_payload_fingerprint.py`. Once a Publication ID exists in the durable ledger, a different payload hash cannot be reclaimed. Editing the delivery payload after the first durable claim requires a new Publication ID.

## Durable Supabase delivery ledger

Production Supabase migration `add_telegram_publication_delivery` is already applied.

Table:

`public.telegram_publication_delivery`

States:

- `pending`
- `claimed`
- `sent`
- `failed`
- `uncertain`

Service-role-only RPCs:

- `claim_telegram_publication`
- `mark_telegram_publication_sent`
- `mark_telegram_publication_failed`
- `mark_telegram_publication_uncertain`
- `release_telegram_publication_failed`
- `reconcile_telegram_publication_sent`
- `get_telegram_publication_delivery`

A database self-test confirmed duplicate claim blocking, explicit failed-release semantics, uncertain blocking, sent reconciliation and zero leftover test records.

## Required Make v3 ordering after Supabase credential authorization

The final production path must be:

```text
Notion candidate
  -> due check
  -> exact SHA-256 payload hash
  -> Supabase atomic claim
  -> Notion In progress / claimed + Delivery Payload Hash
  -> route text/photo/poll/quiz
  -> Telegram send
  -> Supabase mark sent
  -> Notion Published + Telegram Message ID + Published At
```

Definite Telegram failures must mark Supabase `failed` before Notion `Error` where possible.

If Telegram may have accepted a message but durable sent/writeback confirmation is not proven, the record must remain claim-blocking and be treated as `uncertain`. Automatic retry is forbidden.

## Quiz contract

v3 uses the current Telegram Bot API field `correct_option_ids` from Notion `Correct Option IDs JSON`.
The legacy `Correct Option ID` remains migration-only and must not drive v3 delivery.

## Current external blockers

1. Make Supabase credential request is not yet authorized. Credentials are entered only on Make's secure page, never in chat.
2. The latest GitHub Actions attempt did not receive runners (`runner_id = 0`, `steps = []`) for both Linux and macOS jobs. The immediately preceding code head had CI/Ollama/Apple green; treat the current condition as runner/account provisioning until a runner actually executes the latest head.

## Cutover gate

Do not enable v3 until all of these are true:

- latest code head has actually executed and passed CI/Ollama/Apple;
- Supabase Make connection is authorized and RPC mappings are verified;
- Notion queue has no unexpected Ready/In progress/uncertain records;
- no durable ledger record needs reconciliation;
- v2 is disabled;
- read-only `getMe` and `getChat(@iznanka_ugolovki)` preflight passes;
- v3 acceptance tests pass without a public duplicate;
- only then v3 is activated.
