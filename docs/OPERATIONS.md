# Telegram production operations — «Уголовка наизнанку»

This runbook describes the safe operating model for JAFAR's Telegram editorial and publication pipeline.

## 1. Non-negotiable editorial identity

- Channel: `@iznanka_ugolovki` («Уголовка наизнанку»).
- Author: Артур Чернов — **юрист, бывший следователь**.
- Артур Чернов **не является адвокатом**. Generated copy, metadata, prompts and automation must never call him an advocate or imply advocate status.
- The AI may create a draft and recommendations. **AI must never set a publication to `Ready`.**
- `Ready` is the explicit human approval gate.
- Never publish current-case details, personal data, client strategy, invented legal facts, invented metrics or invented sources.
- No technical/test post may be sent to the public channel without explicit operator authorization.

## 2. Current production topology

### Stable scheduler

- Make scenario `7305820`
- Name: `Telegram @iznanka_ugolovki — Production Scheduler v2 — LIVE`
- Expected state while v3 is being developed: **ACTIVE**
- Polling interval: 15 minutes

### Candidate scheduler

- Make scenario `7311904`
- Name: `Telegram @iznanka_ugolovki — Production Scheduler v3 — OFF`
- Expected state before controlled cutover: **INACTIVE**

Never run v2 and v3 against the same `Ready` queue during a cutover test. A single publication must have exactly one active delivery owner.

### Notion editorial database

- Database: `Social Media Content Calendar`
- Database ID: `3d43c9c6-76b4-8031-98da-c2484ffe3cef`
- Data source ID: `3d43c9c6-76b4-80d6-ac3e-000bf86b2d20`

### Durable state

Supabase stores persistent Telegram delivery state in `public.telegram_publication_delivery` and approved visual assets in `public.telegram_visual_assets`.

The Make flow must treat Supabase as the durable idempotency/reconciliation layer. Notion is the editorial and operator-facing state, not the sole protection against duplicate delivery.

## 3. Publication lifecycle

Normal lifecycle:

`Draft → Review → Ready → In progress → Published`

Failure/recovery paths:

- definite pre-send or Telegram failure: `In progress → Error`, durable state `failed`
- response/result is ambiguous: durable state `uncertain`, `Reconciliation Required = true`
- confirmed Telegram delivery: durable state `sent`, Notion `Published`

### Manual approval rule

Only a human/operator may move `Review` to `Ready`.

Before a row may be `Ready`, verify:

- publication text is approved;
- author status is correct;
- legal claims are fact-checked when required;
- privacy risk is low;
- current-case risk is false;
- legal risk is acceptable;
- editorial blockers are empty;
- due date/time is intentional;
- publication type payload is complete;
- visual asset is approved when required.

## 4. v3 pre-send gate

The v3 scheduler is expected to reject a row unless all applicable conditions are satisfied:

- `Platform = Telegram`
- `Status = Ready`
- `Publication ID` present
- `Publish Date` due
- valid publication type: `text`, `photo`, `poll`, `quiz`
- `Fact Check Status = verified` for the current v3 gate
- `Legal Risk = low`
- `Privacy Risk = low`
- `Current Case Risk = false`
- `Delivery State = pending`
- `Reconciliation Required = false`
- `Editorial Blockers` empty
- content/question/options required by the publication type are present
- for text: `Visual Required = false`
- for photo: approved visual resolution must succeed before Telegram is called

A failed gate is not a reason to weaken the gate. Fix the editorial record instead.

## 5. Canonical Notion fields

Core fields:

- `Name`
- `Status`
- `Platform`
- `Publication ID`
- `Publication Type`
- `Content`
- `Caption`
- `CTA`
- `Hashtags`
- `Publish Date`
- `Source Title`
- `Source URL`
- `Question`
- `Options JSON`
- `Correct Option IDs JSON`
- `Explanation`
- `Telegram Message ID`
- `Published At`
- `Last Error`

Safety/editorial fields:

- `Fact Check Status`
- `Fact Check Notes`
- `Source Evidence JSON`
- `Legal Risk`
- `Privacy Risk`
- `Current Case Risk`
- `Editorial Blockers`
- `Author Value Add`
- `Legal Claims JSON`
- `Content Fingerprint`

Delivery fields:

- `Delivery State`
- `Delivery Payload Hash`
- `Reconciliation Required`

Visual fields:

- `Visual Required`
- `Visual Asset Key`
- `Visual Category`
- `Visual Drive File ID` — legacy compatibility only
- `Photo URL` — legacy compatibility only

## 6. Telegram payload contract

### Text

Use `sendMessage`. Telegram text must respect the current model limit enforced by `TelegramPublication`.

### Photo

Preferred v3 path:

`Visual Asset Key + Visual Category → Supabase resolver → approved Base64 → binary → sendPhoto`

Do not pass a `Visual Asset Key` as if it were a URL.

Legacy `Photo URL` remains supported by the Python model for migration compatibility, but new v3 production rows should use approved assets.

### Poll

`Options JSON` is stored as Telegram `InputPollOption`-compatible objects:

```json
[{"text":"Да"},{"text":"Нет"}]
```

### Quiz

Use `correct_option_ids` / `Correct Option IDs JSON`.

Do not regress to the legacy singular `correct_option_id` contract.

## 7. Approved visual assets

Table: `public.telegram_visual_assets`

A production visual must have:

- immutable `asset_key`, e.g. `what_to_do:v1`;
- matching category;
- positive version;
- filename;
- MIME type;
- lowercase 64-character SHA-256;
- non-empty Base64 data;
- `approved = true`;
- `active = true`.

Canonical RPC:

`resolve_telegram_visual_asset(p_asset_key, p_category)`

The resolver is fail-closed. Blank keys/categories, category mismatch, inactive/unapproved assets or missing binary data must stop publication before Telegram.

Do not overwrite an approved asset under the same versioned key. Create a new key/version instead.

## 8. Durable delivery ledger

Table: `public.telegram_publication_delivery`

States:

- `pending` — may be claimed
- `claimed` — one worker owns the delivery attempt
- `sent` — Telegram delivery is confirmed; never resend
- `failed` — definite failure; retry requires explicit operator release
- `uncertain` — delivery outcome is ambiguous; **never automatically resend**

A `Publication ID` is tied to its payload hash. A changed payload is not an ordinary retry. Use a new publication ID if the material itself changed after a delivery attempt.

### Retry rule

Only `failed` may be returned to `pending`, and only through the explicit release operation after the operator understands the failure.

Never release `claimed`, `sent` or `uncertain` for automatic retry.

### Reconciliation rule

For `uncertain`:

1. Do not resend.
2. Check Telegram/channel state manually or through a trustworthy read-only mechanism.
3. If the post is confirmed present, reconcile the ledger to `sent` with the real Telegram message ID.
4. Update Notion to `Published` only after durable state is confirmed.
5. If delivery is confirmed absent, use a documented operator recovery procedure; do not bypass idempotency ad hoc.

## 9. Failure modes

### Notion claim fails after durable claim

- Do not send to Telegram.
- Mark durable state `failed` where the failure is definite.
- Set Notion `Error` where possible.
- Operator may explicitly release failed state after correcting the Notion problem.

### Telegram returns a definite error

- Mark durable state `failed`.
- Notion → `Error`.
- Store only a sanitized error code/message.
- Fix the root cause before explicit retry release.

### Telegram request times out / result is ambiguous

- Mark durable state `uncertain`.
- `Reconciliation Required = true`.
- Do not automatically retry.

### Durable `sent` succeeds but Notion `Published` writeback fails

- Durable ledger remains authoritative: the post is already sent.
- Do not resend.
- Repair only the Notion writeback after verifying the Telegram message ID.

### Visual resolver fails

- Telegram must not be called.
- Treat as a definite pre-send failure.
- Correct/approve the asset or the Notion asset key/category, then explicitly release the failed delivery.

## 10. Production health

`telegram_production_health.py` treats these as hard blockers:

- Notion unavailable;
- Telegram unavailable;
- scheduler unexpectedly disabled when production should be live;
- stale claims;
- uncertain deliveries;
- records requiring reconciliation.

Failed records are warnings rather than automatic retries.

Health checks must remain read-only. They must not call `sendMessage`, `sendPhoto`, `sendPoll` or any other publication method.

## 11. Secret handling

Never place these in source, Notion content, logs, audit metadata or error text:

- Telegram bot token;
- Supabase service-role key;
- Notion integration secret;
- authorization headers;
- API keys/passwords.

Delivery/audit code must sanitize bearer and Telegram-token-like values before persistence.

Connection IDs and scenario IDs may be documented; credentials themselves may not.

## 12. Controlled v3 acceptance procedure

### Pre-send acceptance — safe default

1. Confirm v2 is the only active production scheduler.
2. Confirm v3 is OFF.
3. Confirm no real row is `Ready`/`In progress` for the test path.
4. Create/use an explicitly synthetic test row.
5. Keep it out of v2's live queue or temporarily isolate ownership safely.
6. Block the Telegram send module physically or use a no-send probe.
7. Run v3 once.
8. Verify:
   - Publication ID extraction;
   - exact payload SHA-256;
   - atomic durable claim;
   - Notion claim;
   - visual resolver if photo;
   - Base64-to-binary decode if photo;
   - no Telegram send occurred.
9. Reset synthetic Notion and ledger state.
10. Return v3 to OFF and confirm the live queue is clean.

The photo pre-send path has already been demonstrated with asset `what_to_do:v1`, producing `what_to_do_v1.jpg` as valid JPEG binary. That acceptance did **not** create a public Telegram post.

### Real end-to-end acceptance

A real Telegram send requires explicit operator authorization.

Before that send:

- v2 must be stopped or the test row must be isolated so only one scheduler owns it;
- v3 must have passed pre-send acceptance;
- queue must contain only the intended approved item(s);
- durable state must be `pending`;
- operator must know exactly what will appear publicly.

After success, verify Telegram message ID, durable `sent`, Notion `Published`, `Published At`, and an empty reconciliation flag.

## 13. v2 → v3 cutover

Do not edit v2 in place.

Recommended cutover:

1. Finish code/migration review and automated tests.
2. Verify v3 pre-send acceptance for text/photo/poll/quiz.
3. Ensure no `uncertain`, stale claim or reconciliation-required records exist.
4. Ensure Notion `Ready` queue is understood and approved.
5. Deactivate v2.
6. Confirm v2 has no incomplete execution.
7. Activate v3.
8. Observe the first scheduled execution with a clean/known queue.
9. Verify durable and Notion state after the first real publication.
10. Keep v2 inactive as rollback fallback until v3 has operated cleanly for an agreed observation period.

## 14. Rollback

If v3 behaves unexpectedly:

1. Deactivate v3 immediately.
2. Do **not** blindly reactivate v2 if there are `claimed`, `sent` or `uncertain` v3 records.
3. Reconcile all in-flight durable records first.
4. Confirm the Notion queue contains no stale `In progress` rows.
5. Return safe rows to a known editorial state only after reconciliation.
6. Reactivate v2 only when duplicate-delivery risk is zero.

Rollback is a state-reconciliation operation, not just a scenario toggle.

## 15. Deprecated / temporary scenarios

Do not reactivate historical or temporary scenarios without a specific reviewed purpose. In particular, do not blindly reactivate IDs previously superseded during Telegram testing (`6855238`, `7274887`, `7305466`, `7305508`, `7305212`, `7306564`).

One-off reset/probe utilities used during acceptance must remain inactive after use.

## 16. Definition of production-ready v3

v3 is ready for cutover only when all of the following are true:

- human `Ready` gate preserved;
- author status rule enforced;
- legal fact-check is fail-closed;
- privacy/current-case/legal risk gates are active;
- persistent atomic delivery ledger is active;
- uncertain delivery cannot auto-retry;
- approved visual resolver is source-controlled and tested;
- photo binary path passes pre-send acceptance;
- current poll/quiz API contract is used;
- health/readiness checks are read-only;
- automated tests/linters are green on a working runner;
- operations runbook is current;
- no secrets are present;
- no public technical test is sent without explicit authorization.
