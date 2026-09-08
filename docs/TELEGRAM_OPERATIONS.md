# Telegram production operations — «Уголовка наизнанку»

## Purpose

This runbook governs the production publishing path for `@iznanka_ugolovki`.
The system is fail-closed: a publication is sent only after explicit human approval and all machine gates pass.

Author identity is fixed: Артур Чернов is a lawyer and former investigator. He is **not an advocate (адвокат)**.
AI is never allowed to promote a publication to `Ready`.

## Canonical editorial lifecycle

`Draft -> Review -> Ready -> In progress -> Published`

Exceptional states:

- `Error`: a definite failure occurred before a successful Telegram delivery was established.
- delivery `uncertain`: Telegram may have accepted the message but durable writeback is not proven. Never retry automatically.
- `Reconciliation Required = true`: operator inspection is mandatory before any new send attempt.

## Publication gates

A production sender must require all of the following:

1. Platform is `Telegram`.
2. Status is `Ready`.
3. `Publish Date` is present and due.
4. Publication Type is one of `text`, `photo`, `poll`, `quiz`.
5. Fact Check Status is `verified`, or `not_required` only when the material contains no factual/legal claim needing verification.
6. Legal Risk is `low` for automatic delivery. Medium/high/critical material returns to manual review.
7. Privacy Risk is `low`.
8. Current Case Risk is false.
9. Editorial Blockers is empty.
10. Delivery State is `pending`.
11. Reconciliation Required is false.
12. Required type-specific fields are complete and valid.
13. The delivery ledger atomically claims the Publication ID with the exact payload hash.

## Type-specific validation

### text
- Content is non-empty.
- Telegram text limit is respected.

### photo
- Photo URL is a valid HTTP(S) URL.
- Caption respects Telegram's caption limit.

### poll
- Question is present.
- Options JSON is an array of Telegram `InputPollOption` objects, stored canonically as objects with `text`.
- No quiz-only correct answer field is sent.

### quiz
- Question and options are present.
- `Correct Option IDs JSON` contains a monotonically increasing JSON array of valid zero-based option indexes.
- Production uses Telegram Bot API `correct_option_ids`; the legacy single `Correct Option ID` exists only for migration compatibility and must not drive v3.

## Delivery ledger

The durable ledger is `public.telegram_publication_delivery`.

States:

- `pending`: eligible to be claimed.
- `claimed`: one sender owns the delivery attempt.
- `sent`: terminal; never send again.
- `failed`: definite failure; retry only after explicit operator release.
- `uncertain`: terminal until reconciliation; never retry automatically.

The claim RPC is atomic and binds `publication_id` to `payload_hash`. A changed payload under the same Publication ID must fail closed.

## Failure handling

### Definite Telegram API failure

1. Mark durable delivery `failed`.
2. Set Notion Status `Error`.
3. Set Notion Delivery State `failed`.
4. Store a sanitized Last Error code/message; never store bot tokens, Authorization headers or secrets.
5. Human reviews cause before releasing the failed record for retry.

### Telegram may have sent, but writeback failed

This is the dangerous case.

1. Mark durable delivery `uncertain` if the ledger write is still reachable.
2. Set Notion Delivery State `uncertain` when possible.
3. Set Reconciliation Required true.
4. Do **not** retry.
5. Inspect the target channel and Make/GitHub/Supabase audit evidence.
6. If the message exists, reconcile with its Telegram Message ID and mark `sent`/`Published`.
7. If it can be proven no message was sent, operator may reset through the documented recovery path; never infer absence from a timeout alone.

## Preflight before enabling a new scheduler

- GitHub CI: green.
- Ollama Integration: green.
- Jafar Apple: green.
- Notion connection: healthy.
- Telegram connection: healthy (`getMe` and target chat access verified).
- No `uncertain` deliveries.
- No records requiring reconciliation.
- No stale claims.
- Zero unexpected `Ready` cards.
- v2 and v3 must never both be active.
- v3 must first be tested while inactive/offline from the public channel.

## v2 -> v3 cutover

1. Keep v2 live while v3 is built and inspected.
2. Create v3 inactive.
3. Validate mappings, filters and branch payloads.
4. Run non-public/dry-run acceptance tests.
5. Confirm production health snapshot has no blockers.
6. Deactivate v2.
7. Confirm v2 is inactive and has no incomplete execution.
8. Activate v3.
9. Observe first due publication end-to-end.
10. Verify Notion `Published`, Telegram Message ID, Published At and durable ledger `sent` agree.

## Rollback

If v3 fails before a Telegram message is accepted:

1. Deactivate v3.
2. Resolve/reconcile all `claimed`, `failed` and `uncertain` records.
3. Only after no ambiguous delivery remains, reactivate the last known-good scheduler if its payload contract is still valid.

Never reactivate v2 while v3 has an unresolved claim or uncertain delivery for the same Publication ID.

## Weekly editorial analytics

Analytics must use observed data only. Missing metrics stay `None`/unavailable; they are never converted to zero.
The report format is:

`ФАКТ -> ЧТО ЭТО ОЗНАЧАЕТ -> ПОЧЕМУ -> ЧТО ДЕЛАТЬ ДАЛЬШЕ`

Review at minimum: best/weak posts, views, forwards, subscriber growth/churn when available, advertising sources/cost, retention and real client inquiries.
