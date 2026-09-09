# Telegram production operations — «Уголовка наизнанку»

This runbook describes the current safe operating model for JAFAR's Telegram editorial and publication pipeline.

## CURRENT PRODUCTION STATE

- **Primary runtime:** Supabase Cloud.
- **Primary publication chain:** Notion → Supabase → Telegram.
- **Make v2 (`7305820`):** rollback-only and inactive.
- **MacBook:** not required for scheduled publication.
- Cloud publisher: enabled, non-dry-run.
- Notion sync: enabled, non-dry-run.
- Publisher cron: every minute; Notion sync cron: every five minutes.
- Production destination: Telegram channel chat ID `-1004412524447`.

This state is operational configuration, not permission to create an unscheduled test post.
No diagnostic procedure in this runbook sends Telegram content.

## 1. Non-negotiable editorial identity

- Channel: `@iznanka_ugolovki` («Уголовка наизнанку»).
- Author: Артур Чернов — **юрист, бывший следователь**.
- Артур Чернов **не является адвокатом**. Generated copy, prompts and automation must never call him an advocate or imply advocate status.
- Work only from the user-approved content plan. Do not invent an extra publication merely to preserve frequency.
- Never publish current-case details, personal data, client strategy, invented legal facts, invented metrics or invented sources.
- No technical/test post may be sent to the public channel without explicit operator authorization.

## 2. Current production topology — after 2026-09-09 cutover

Primary runtime is now Supabase Cloud and does not depend on an always-on MacBook, GitHub Actions, or Make operations.

Production path:

`approved Notion plan item → Status=Ready → telegram-notion-sync-v3 → telegram_publication_queue → telegram-publisher-v3 → telegram-egress → Telegram → durable SENT → Notion writeback`

### Supabase Cloud — LIVE

- `telegram-notion-sync-v3`
  - cron: every 5 minutes
  - config: `enabled=true`, `dry_run=false`
  - reads Telegram + Ready Notion items
  - upserts only safe `pending` queue rows
  - writes terminal delivery state back to Notion
- `telegram-publisher-v3`
  - cron: every minute
  - config: `enabled=true`, `dry_run=false`
  - sends only due `Ready/pending` rows after all gates pass
- `telegram-notion-guard-v3`
  - read-only final Notion revalidation before atomic claim
  - prevents publication of a stale Supabase row if Notion was changed or canceled after sync
- `telegram-egress`
  - `verify_jwt=true`
  - additionally requires the service-role Bearer internally
  - allowlisted chat IDs only
- `telegram-bot-access-v3`
  - **retired after cutover verification**
  - now returns HTTP 410 and requires JWT
  - not part of production runtime

### Make — rollback only

Scenario `7305820` is intentionally **INACTIVE** and renamed:

`Telegram @iznanka_ugolovki — Production Scheduler v2 — ROLLBACK (OFF)`

Do not reactivate it while Supabase Cloud Publisher is live unless the rollback procedure below has been completed and duplicate-delivery risk is zero.

Make v3 scenario `7311904` remains experimental/off and is not part of production.

### Notion

Database: `Social Media Content Calendar`

- Database ID: `3d43c9c6-76b4-8031-98da-c2484ffe3cef`
- Data source ID: `3d43c9c6-76b4-80d6-ac3e-000bf86b2d20`

Notion is the editorial/operator-facing source. Supabase is the durable delivery authority.

### Supabase durable state

- `public.telegram_publication_queue` — cloud delivery queue and Notion linkage.
- `public.telegram_publication_delivery` — persistent idempotency/delivery ledger.
- `public.telegram_visual_assets` — versioned operator-approved visual assets.

## 3. Publication lifecycle

Normal lifecycle:

`Draft → Review → Ready → In progress/claimed → Published/sent`

A planned item may be moved to `Ready` only by a human operator when it is already part
of the user-approved content plan and all safety/editorial checks are complete. AI may
create or revise `Draft`/`Review`; it never supplies the `Ready` decision.

Before `Ready`, verify:

- `Platform=Telegram`;
- `Publication ID` is present and unique;
- `Publish Date` is the approved date/time;
- `Publication Type` is valid;
- `Content Fingerprint` is a lowercase 64-character SHA-256;
- `Fact Check Status` is `verified` or `not_required`;
- `Legal Risk=low`;
- `Privacy Risk=low`;
- `Current Case Risk=false`;
- `Editorial Blockers` is empty;
- `Delivery State=pending`;
- `Reconciliation Required=false`;
- `Telegram Message ID` is empty;
- type-specific payload is complete;
- approved visual asset is assigned for `photo`.

## 4. Final Notion revalidation

Supabase queue state is not sufficient by itself.

Immediately before atomic claim, `telegram-publisher-v3` calls `telegram-notion-guard-v3` for the source page. Publication is blocked if the current Notion page no longer matches the queued item.

The guard rechecks at least:

- Platform and Status;
- Publication ID and type;
- Publish Date;
- Content Fingerprint;
- Fact Check Status;
- legal/privacy/current-case risk;
- Editorial Blockers;
- Delivery State / Reconciliation Required / Telegram Message ID;
- text/caption or poll/quiz payload;
- visual asset key/category for photo.

This prevents a post that was changed from `Ready` to `Review` from being sent from a stale queue row.

## 5. Telegram payload contract

### Text

`text` means one `sendMessage` operation. `Visual Required=false`.

### Photo

Preferred path:

`Visual Asset Key + Visual Category → resolve_telegram_visual_asset → approved Base64 → telegram-egress sendPhoto`

Do not use `Visual Drive File ID` or `Photo URL` as the primary production path.

### Poll

Use a JSON list of InputPollOption-compatible objects, for example:

```json
[{"text":"Да"},{"text":"Нет"}]
```

### Quiz

Use `correct_option_ids` / `Correct Option IDs JSON`. Do not regress to legacy singular `correct_option_id`.

## 6. Approved visual assets

A production asset must have:

- immutable versioned `asset_key`, e.g. `what_to_do:v1`;
- matching category;
- positive version;
- filename and MIME type;
- lowercase 64-character SHA-256;
- non-empty Base64 data;
- `approved=true`;
- `active=true`.

Canonical RPC:

`resolve_telegram_visual_asset(p_asset_key, p_category)`

It is fail-closed. Invalid/missing/unapproved assets stop publication before Telegram.

## 7. Durable delivery and idempotency

States:

- `pending` — eligible for atomic claim;
- `claimed` — one attempt owns the publication;
- `sent` — confirmed; never resend;
- `failed` — definite pre-send failure; explicit operator release required;
- `uncertain` — Telegram may have accepted the message; never automatically retry.

The payload hash is tied to the Publication ID. Do not mutate a previously attempted publication into a different message and treat it as the same retry.

### Direct Telegram error rule

Any ambiguous transport/non-OK result after atomic claim becomes `uncertain`, not retryable `failed`.

On `uncertain`:

- do not resend;
- set `Reconciliation Required=true`;
- preserve any known Telegram Message ID;
- reconcile against trustworthy Telegram/durable evidence.

### Database commit ambiguity

If Telegram returns a message ID but Supabase SENT commit is ambiguous, publisher rechecks durable delivery. If SENT with the same ID is confirmed, the result is accepted; otherwise state becomes `uncertain`.

### Normal flow

`Ready/pending → final Notion guard → atomic claimed → Telegram send → durable sent/message_id → Notion Published`

### Failure flow

- A definite validation or configuration failure before claim creates no Telegram attempt.
- Once a send begins, any transport/non-OK/missing-response ambiguity becomes `uncertain`.
- If durable `sent` exists and Notion writeback fails, repair only Notion. Never resend.

## 8. Secret handling and egress security

Never place in source, Notion content, logs, audit metadata or error text:

- Telegram bot token;
- Supabase service-role key;
- Notion integration secret;
- worker authentication secret;
- authorization headers.

Production secrets live in Supabase Vault/runtime.

`telegram-egress` is protected twice:

1. Supabase JWT verification;
2. exact service-role Bearer check inside the function.

A normal anon/authenticated Supabase JWT is insufficient to send through the bot.

## 9. Historical bot/channel access verification

A temporary read-only probe was used during the 2026-09-09 cutover for Telegram `getMe` and `getChatMember` only. It confirmed:

- bot username `Djafar23_bot`;
- bot ID `8551049942`;
- channel membership status `administrator`;
- `can_post_messages=true`;
- `can_edit_messages=true`;
- `can_delete_messages=true`.

No Telegram message was created by this probe. The probe was then retired: `telegram-bot-access-v3` now requires JWT and returns HTTP 410.

## 10. Production health

At normal idle health:

- cloud sync enabled/non-dry;
- cloud publisher enabled/non-dry;
- Telegram token present;
- `due_ready_count=0` unless a post is due;
- `claimed_count=0` outside an active send;
- `uncertain_count=0`;
- no reconciliation-required rows;
- Make v2 inactive.

The read-only health contract is implemented in
`src/jafar/telegram_production_health.py`. It treats disabled/non-live cloud configs,
missing token, inactive/stale/non-successful cron, stale claims, uncertain deliveries,
reconciliation work, or an active Make v2 as blockers. Failed rows and short-lived
non-stale claims are surfaced without automatically retrying them.

Cron jobs:

- publisher: `* * * * *`;
- Notion sync: `*/5 * * * *`.

A ChatGPT condition-watch named `TG cloud health` checks the cloud configs, cron freshness, due/claimed/uncertain state, reconciliation flags and that Make v2 remains inactive. It must notify only on a real problem and must never perform a Telegram send or retry as a diagnostic action.

Cron SQL success alone does not prove Telegram delivery. Durable SENT + real Telegram message ID is authoritative for a completed publication.

## 11. Cutover record — 2026-09-09

The cloud cutover was performed in an empty Ready window.

Verified before/at cutover:

- Notion Ready count: 0;
- Supabase due-ready count: 0;
- claimed count: 0;
- uncertain count: 0;
- Telegram token present;
- bot administrator/posting rights confirmed by read-only Bot API probe;
- Make v2 had zero incomplete executions and was deactivated;
- Notion cloud sync passed `200 OK`;
- publisher runtime became `enabled=true`, `dry_run=false`.

The first real scheduled Cloud Publisher delivery after this cutover must be observed and verified with durable SENT, Telegram Message ID and Notion Published writeback.

## 12. Rollback to Make v2

If cloud publisher behaves unexpectedly:

1. Set `telegram_publisher_config.enabled=false` immediately.
2. Do not reactivate Make while any cloud record is `claimed`, `sent` but not reconciled, or `uncertain`.
3. Reconcile in-flight durable records and Notion state.
4. Confirm `claimed_count=0`, `uncertain_count=0`, no reconciliation-required rows, and no due cloud item can still send.
5. Only then reactivate Make scenario `7305820`.
6. Keep cloud publisher disabled until the root cause is fixed and a new cutover is prepared.

Rollback is a delivery-state reconciliation operation, not just a toggle.

## 13. Scheduled editorial task

The ChatGPT task `TG контент по плану` may prepare only items already in the user-approved plan.

It must not call Make or Telegram directly. It may leave a complete safe Notion card in
`Review`. A human operator performs the explicit `Review → Ready` transition; Supabase
Cloud then handles delivery.

For photo posts it must use approved `Visual Asset Key + Visual Category`. Legacy Drive ID / Photo URL are not the primary production path.

If there is no approved planned card, it must not invent one.

## 14. Source control and CI

Canonical implementation is maintained in PR #71 / branch `feat/jafar-production-complete`.

GitHub Actions runner/budget availability is not part of the production runtime. Runtime continues on Supabase even when GitHub-hosted CI cannot obtain a runner.

Do not claim full CI green unless a runner actually executed the tests.

## 15. Deprecated / temporary scenarios

Do not blindly reactivate historical scenario IDs `6855238`, `7274887`, `7305466`, `7305508`, `7305212`, `7306564`.

Make v3 `7311904` is not production. `telegram-bot-access-v3` is retired. Probe/test utilities must not be used to send hidden public technical posts.

## 16. Remaining acceptance item

The architecture and no-send/pre-send tests are complete enough for cloud production ownership, but the **first real post delivered by Supabase Cloud after cutover remains the final live acceptance event**.

After that post, verify all three layers agree:

`Telegram message exists ↔ durable ledger = sent with same message ID ↔ Notion = Published/sent`
