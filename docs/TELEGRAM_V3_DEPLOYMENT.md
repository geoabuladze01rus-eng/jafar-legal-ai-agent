# Telegram Scheduler v3 deployment contract

This document pins the production migration contract for Telegram channel `@iznanka_ugolovki`.

## Live / candidate scenarios

- Current live Make scenario: `7305820` — `Telegram @iznanka_ugolovki — Production Scheduler v2 — LIVE`.
- Candidate Make scenario: `7311904` — `Telegram @iznanka_ugolovki — Production Scheduler v3 — OFF`.
- Read-only Telegram preflight: `7311962` — `TEMP — Telegram v3 Read-Only Preflight`.
- Supabase preflight: `7312653` — temporary on-demand scenario, kept OFF outside controlled maintenance windows.

The Make plan currently allows only one active scenario. v2 and v3 must therefore never be active at the same time. Preflight scenarios are executed only inside a controlled maintenance window after v2 is disabled. v2 is restored immediately after each read-only/non-Telegram test.

## v3 safety gate

A candidate can reach SHA-256 calculation and durable claim only when all applicable conditions are true:

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

The pre-claim safety gate is attached before the SHA-256/Supabase modules. Future, risky, unverified, incomplete and unapproved cards therefore never create durable ledger claims.

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

Production Supabase migration `add_telegram_publication_delivery` is applied.

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

Make Supabase credential is authorized as connection `10685225`.

### Make Supabase API-call serialization rule

The Make `supabase:makeAnApiCall` module must receive RPC arguments as a **raw JSON string** in `body`, with `Content-Type: application/json`.

Passing a Make collection/object as `body` was empirically rejected by PostgREST as a zero-argument RPC call. Raw JSON was then verified successfully.

Example shape:

```json
{"p_publication_id":"...","p_payload_hash":"..."}
```

All v3 Supabase claim/SENT/FAILED modules use the raw-JSON contract.

## Verified Make / Supabase smoke tests

A controlled Make smoke test used a temporary Publication ID and a 64-character test hash:

1. First `claim_telegram_publication` call returned `body = true`.
2. Second call with the same Publication ID/hash returned `body = false`.
3. The test ledger row was deleted after verification.
4. Cleanup query confirmed `remaining = 0`.

This verifies Make credential authorization, PostgREST RPC serialization, atomic claim behavior and duplicate blocking.

A prior direct database self-test also confirmed explicit failed-release semantics, uncertain blocking and sent reconciliation.

## Required Make v3 ordering

The production path is:

```text
Notion candidate
  -> due/risk/fact-check/type pre-claim gate
  -> exact SHA-256 payload hash
  -> Supabase atomic claim
  -> claim result must be true
  -> Notion In progress / claimed + Delivery Payload Hash
  -> route text/photo/poll/quiz
  -> Telegram send
  -> Supabase mark sent
  -> Notion Published + Telegram Message ID + Published At
```

Definite Telegram failures must leave the durable ledger claim-blocking or transition it to `failed`; automatic retry is never allowed merely because a Notion writeback failed.

If Telegram has returned a message id but durable SENT persistence fails, Notion is written as `Error + uncertain + Reconciliation Required = true` with the captured Telegram Message ID. Automatic retry is forbidden.

If the final Notion Published writeback fails after Supabase is already `sent`, Notion is also moved into reconciliation workflow; the durable `sent` state prevents a duplicate post.

## Telegram preflight verification

Controlled read-only Make execution `2a208f1f50274c8bb31d9b5682a018de` succeeded:

- `getMe` returned HTTP 200, bot id `8551049942`, username `@Djafar23_bot`;
- `getChat(@iznanka_ugolovki)` returned HTTP 200 and channel id `-1004412524447`.

No Telegram message was sent.

## v3 empty-queue smoke test

Controlled Make execution `00ace69ec28d42a49f81c477f91720dd` succeeded with exactly three modules executed:

1. BasicTrigger
2. Notion search
3. Publish Date calculation

No SHA-256, Supabase claim, Notion claim or Telegram module ran because the queue was empty. v3 was then disabled and v2 restored LIVE.

## Quiz contract

v3 uses the current Telegram Bot API field `correct_option_ids` from Notion `Correct Option IDs JSON`.
The legacy `Correct Option ID` remains migration-only and must not drive v3 delivery.

## Current external blocker

The latest GitHub Actions attempt on a previous head did not receive runners (`runner_id = 0`, `steps = []`) for both Linux and macOS jobs. An earlier code head had CI/Ollama/Apple green. The latest branch head must still receive real runners and pass before cutover.

## Cutover gate

Do not enable v3 as production until all of these are true:

- latest code head has actually executed and passed CI/Ollama/Apple;
- Notion queue has no unexpected Ready/In progress/uncertain records;
- no durable ledger record needs reconciliation;
- v2 is disabled in the controlled cutover window;
- read-only `getMe` and `getChat(@iznanka_ugolovki)` preflight passes;
- v3 acceptance tests pass without a public duplicate;
- only then v3 is activated.
