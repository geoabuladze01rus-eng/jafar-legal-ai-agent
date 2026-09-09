# Telegram production operations — «Уголовка наизнанку»

This runbook describes the safe operating model for JAFAR's Telegram editorial and publication pipeline.

## 1. Non-negotiable editorial identity

- Channel: `@iznanka_ugolovki` («Уголовка наизнанку»).
- Author: Артур Чернов — **юрист, бывший следователь**.
- Артур Чернов **не является адвокатом**. Generated copy, prompts and automation must never call him an advocate or imply advocate status.
- AI may create `Review` drafts and recommendations. **AI must never set `Ready` or `Published`.**
- `Ready` is the explicit human approval gate.
- Never publish current-case details, personal data, client strategy, invented legal facts, invented metrics or invented sources.
- No technical/test post may be sent to the public channel without explicit operator authorization.

## 2. Current production topology

### Stable scheduler

- Make scenario `7305820`
- `Telegram @iznanka_ugolovki — Production Scheduler v2 — LIVE`
- Expected state while v3 is being developed: **ACTIVE**
- Polling interval: 15 minutes

### Candidate scheduler

- Make scenario `7311904`
- `Telegram @iznanka_ugolovki — Production Scheduler v3 — OFF`
- Expected state before controlled cutover: **INACTIVE**

Never let v2 and v3 own the same `Ready` queue during a cutover test.

### Notion

Database: `Social Media Content Calendar`

- Database ID: `3d43c9c6-76b4-8031-98da-c2484ffe3cef`
- Data source ID: `3d43c9c6-76b4-80d6-ac3e-000bf86b2d20`

### Supabase durable state

- `public.telegram_publication_delivery` — persistent delivery/idempotency ledger.
- `public.telegram_visual_assets` — versioned operator-approved visual assets.

Notion is the editorial/operator-facing state. Supabase is the durable protection against duplicate delivery.

## 3. Publication lifecycle

Normal lifecycle:

`Draft → Review → Ready → In progress → Published`

Only a human/operator may move `Review → Ready`.

Before `Ready`, verify:

- text is approved;
- author status is correct;
- legal claims are fact-checked when required;
- privacy risk is low;
- current-case risk is false;
- legal risk is acceptable;
- editorial blockers are empty;
- due date/time is intentional;
- type-specific payload is complete;
- approved visual asset is assigned for `photo`.

## 4. v3 pre-send gate

v3 must reject a row unless all applicable conditions are satisfied:

- `Platform = Telegram`
- `Status = Ready`
- `Publication ID` present
- `Publish Date` due
- `Publication Type ∈ {text, photo, poll, quiz}`
- `Fact Check Status ∈ {verified, not_required}`
- `Legal Risk = low`
- `Privacy Risk = low`
- `Current Case Risk = false`
- `Delivery State = pending`
- `Reconciliation Required = false`
- `Editorial Blockers` empty
- type-specific content/question/options present
- for `text`: `Visual Required = false`
- for `photo`: approved visual resolver must succeed before Telegram is called

`pending`, `unverified`, `failed` or an unknown fact-check state must not pass.

A failed gate is not a reason to weaken the gate. Fix the editorial record instead.

## 5. Canonical Notion fields

Core:

- `Name`, `Status`, `Platform`, `Publication ID`, `Publication Type`
- `Content`, `Caption`, `CTA`, `Hashtags`
- `Publish Date`, `Source Title`, `Source URL`
- `Question`, `Options JSON`, `Correct Option IDs JSON`, `Explanation`
- `Telegram Message ID`, `Published At`, `Last Error`

Safety/editorial:

- `Fact Check Status`, `Fact Check Notes`, `Source Evidence JSON`
- `Legal Risk`, `Privacy Risk`, `Current Case Risk`
- `Editorial Blockers`, `Author Value Add`, `Legal Claims JSON`
- `Content Fingerprint`

Delivery:

- `Delivery State`, `Delivery Payload Hash`, `Reconciliation Required`

Visual:

- `Visual Required`
- `Visual Asset Key`
- `Visual Category`
- `Visual Drive File ID` — legacy compatibility only
- `Photo URL` — legacy compatibility only

## 6. Telegram payload contract

### Text

`text` means one `sendMessage` operation and has no mandatory media. AI may still suggest an `image_prompt`, but that recommendation is not a delivery dependency for a text message.

### Photo

Preferred v3 path:

`Visual Asset Key + Visual Category → Supabase resolver → approved Base64 → binary → sendPhoto`

Do not pass a `Visual Asset Key` as if it were a URL.

### Poll

`Options JSON` is a JSON-serialized list of `InputPollOption`-compatible objects, for example:

```json
[{"text":"Да"},{"text":"Нет"}]
```

### Quiz

Use `correct_option_ids` / `Correct Option IDs JSON`.

Do not regress to legacy singular `correct_option_id`.

## 7. Approved visual assets

A production asset must have:

- immutable versioned `asset_key`, e.g. `what_to_do:v1`;
- matching category;
- positive version;
- filename and MIME type;
- lowercase 64-character SHA-256;
- non-empty Base64 data;
- `approved = true`;
- `active = true`.

Canonical RPC:

`resolve_telegram_visual_asset(p_asset_key, p_category)`

It is fail-closed. Blank/mismatched keys, inactive/unapproved assets, invalid hash or missing binary must stop publication before Telegram.

Do not overwrite approved content under an existing versioned key. Create a new key/version.

## 8. Durable delivery ledger

States:

- `pending` — may be claimed
- `claimed` — one delivery attempt owns the publication
- `sent` — delivery confirmed; never resend
- `failed` — definite **pre-send** failure; retry requires explicit operator release
- `uncertain` — outcome may include a successful Telegram send; never automatically retry

A `Publication ID` is tied to its payload hash. If content/payload changes after an attempt, create a new Publication ID rather than pretending it is the same retry.

### Critical send-error rule

Until Make exposes and we validate a reliable error classification that proves Telegram could not have accepted a request, **any error raised directly by a Telegram send module is treated as `uncertain`**, not `failed`.

This applies to text, photo, poll and quiz.

On direct send error:

- durable ledger → `uncertain`;
- Notion → `Error`;
- `Delivery State = uncertain`;
- `Reconciliation Required = true`;
- `Last Error` must say `DO NOT RETRY`;
- no automatic release/retry.

This conservative rule prevents duplicate public posts after timeouts, connection drops or lost responses.

### Explicit retry rule

Only a genuinely definite `failed` record may be returned to `pending`, and only through the explicit operator release RPC after the failure is understood.

Never release `claimed`, `sent` or `uncertain` as an ordinary retry.

### Reconciliation rule

For `uncertain`:

1. Do not resend.
2. Check Telegram/channel state manually or through a trustworthy read-only mechanism.
3. If the post exists, reconcile durable state to `sent` with the real Telegram message ID.
4. Repair Notion `Published` state only after durable state is confirmed.
5. If delivery is proven absent, use a documented operator recovery procedure; never bypass idempotency ad hoc.

## 9. Failure modes

### Notion claim fails after durable claim

Telegram has not been called yet. This is a definite pre-send failure and may be recorded `failed`. Correct the Notion issue before explicit release.

### Visual resolver fails

Telegram has not been called. Record a definite pre-send failure, correct/approve the asset or key/category, then explicitly release if appropriate.

### Telegram send module errors

Outcome is ambiguous by default. Record `uncertain`, require reconciliation, **do not retry**.

### Telegram succeeds but Supabase `sent` commit fails

Notion must show `uncertain` and preserve the returned Telegram Message ID when available. Do not resend; reconcile durable state.

### Supabase `sent` succeeds but Notion `Published` writeback fails

Durable ledger is authoritative: the message is already sent. Do not resend. Repair Notion writeback only.

## 10. Production health

`telegram_production_health.py` treats these as hard blockers:

- Notion unavailable;
- Telegram unavailable;
- production scheduler unexpectedly disabled;
- stale claims;
- uncertain deliveries;
- reconciliation-required records.

Failed records are warnings, not automatic retries.

Health checks must remain read-only and must not call publication methods.

## 11. Secret handling

Never place these in source, Notion content, logs, audit metadata or error text:

- Telegram bot token;
- Supabase service-role key;
- Notion integration secret;
- authorization headers;
- API keys/passwords.

Delivery/audit code must sanitize bearer and Telegram-token-like values before persistence.

Connection/scenario IDs may be documented; credentials may not.

## 12. Controlled v3 acceptance

Safe default is **pre-send acceptance**, not a public test.

1. Confirm v2 is the only active production scheduler.
2. Confirm v3 is OFF.
3. Confirm the live `Ready`/`In progress` queue is understood and clean.
4. Use an explicitly synthetic row.
5. Ensure v2 cannot consume the synthetic row during the test.
6. Physically block the target Telegram send module or use a no-send probe.
7. Run one controlled v3 execution.
8. Verify Publication ID, exact payload hash, atomic durable claim, Notion claim, and type-specific pre-send processing.
9. For photo, verify resolver + Base64-to-binary conversion.
10. Confirm no Telegram send occurred.
11. Reset synthetic Notion/ledger state.
12. Return v3 to OFF and restore the stable production scheduler state.

The photo pre-send path has already been demonstrated with `what_to_do:v1` → `what_to_do_v1.jpg` and valid binary decode. That acceptance created no public Telegram post.

A real Telegram E2E send requires explicit operator authorization.

## 13. v2 → v3 cutover

1. Finish code/migration review and automated gates.
2. Pass pre-send acceptance for text/photo/poll/quiz.
3. Ensure there are no uncertain deliveries, stale claims or reconciliation-required rows.
4. Review every `Ready` item.
5. Deactivate v2 and confirm it has no incomplete execution.
6. Activate v3.
7. Observe the first scheduled run with a known queue.
8. Verify durable `sent`, real Telegram Message ID and Notion `Published` after the first real publication.
9. Keep v2 inactive as rollback fallback during an observation period.

## 14. Rollback

If v3 behaves unexpectedly:

1. Deactivate v3 immediately.
2. Do not blindly reactivate v2 while any v3 record is `claimed`, `sent` or `uncertain`.
3. Reconcile durable in-flight records.
4. Repair stale Notion `In progress` state only after reconciliation.
5. Reactivate v2 only when duplicate-delivery risk is zero.

Rollback is a state-reconciliation operation, not just a scenario toggle.

## 15. Deprecated / temporary scenarios

Do not blindly reactivate historical scenario IDs `6855238`, `7274887`, `7305466`, `7305508`, `7305212`, `7306564`.

One-off reset/probe utilities must remain inactive after use.

## 16. Definition of production-ready v3

v3 is ready only when:

- human `Ready` gate is preserved;
- author status rule is enforced;
- fact-check is fail-closed with only `verified | not_required` accepted;
- privacy/current-case/legal risk gates are active;
- persistent atomic ledger is active;
- direct Telegram send errors become `uncertain`, not retryable `failed`;
- approved visual resolver is source-controlled and tested;
- photo binary path passes pre-send acceptance;
- current poll/quiz API contract is used;
- health checks are read-only;
- automated tests/linters are green on a working runner;
- no secrets are present;
- no public technical test is sent without explicit authorization.
