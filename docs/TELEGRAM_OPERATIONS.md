# Telegram production operations — «Уголовка наизнанку»

## Purpose

This runbook governs the production publishing path for `@iznanka_ugolovki`.
The system is fail-closed: a publication is sent only after explicit human approval and all machine gates pass.

Author identity is fixed: Артур Чернов is a lawyer and former investigator. He is **not an advocate (адвокат)**.
AI is never allowed to promote a publication to `Ready`.

## Canonical editorial lifecycle

`Draft -> Review -> Ready -> In progress -> Published`

Exceptional states:

- `Error`: a definite failure occurred or an operator action is required.
- delivery `failed`: Telegram definitely failed; retry is possible only after explicit durable release.
- delivery `uncertain`: delivery/writeback is ambiguous. Never retry automatically.
- `Reconciliation Required = true`: operator reconciliation is mandatory before any new send attempt.

## Publication gates

A production sender must require all of the following:

1. Platform is `Telegram`.
2. Status is `Ready`.
3. `Publication ID` is present.
4. `Publish Date` is present and due.
5. Publication Type is one of `text`, `photo`, `poll`, `quiz`.
6. Fact Check Status is `verified` for the production Make v3 automatic path.
7. Legal Risk is `low`.
8. Privacy Risk is `low`.
9. Current Case Risk is false.
10. Editorial Blockers is empty.
11. Delivery State is `pending`.
12. Reconciliation Required is false.
13. Required type-specific fields are complete and valid.
14. The delivery ledger atomically claims the Publication ID with the exact payload hash.

No card may reach SHA-256 or the durable ledger before these gates pass.

## Type-specific validation

### text
- Content is non-empty.
- Telegram text limit is respected.

### photo
- Photo URL is a valid HTTP(S) URL.
- Caption respects Telegram's caption limit.

### poll
- Question is present.
- Options JSON is valid for Telegram `sendPoll`.
- No quiz-only correct answer field is sent.

### quiz
- Question and options are present.
- `Correct Option IDs JSON` is present and valid for the Telegram Bot API contract.
- Production v3 uses `correct_option_ids`; legacy single `Correct Option ID` is migration-only.

## Delivery ledger

The durable ledger is `public.telegram_publication_delivery`.

States:

- `pending`: eligible to be claimed.
- `claimed`: one sender owns the delivery attempt.
- `sent`: terminal; never send again.
- `failed`: definite failure; retry only after explicit operator release.
- `uncertain`: terminal until reconciliation; never retry automatically.

The claim RPC is atomic and binds `publication_id` to `payload_hash`. A changed payload under the same Publication ID must fail closed. Use a new Publication ID for a changed delivery payload.

## Normal production order

```text
Notion Ready card
  -> safety/due/type/fact-check/risk gate
  -> extract Publication ID
  -> SHA-256 delivery payload hash
  -> Supabase atomic claim
  -> claim must return true
  -> Notion In progress / claimed
  -> Telegram send
  -> normalize Telegram Message ID to number
  -> Supabase SENT
  -> atomic Notion Published writeback
```

The final Notion writeback is an authorized Notion API PATCH that atomically sets:

- Status `Published`;
- Delivery State `sent`;
- numeric Telegram Message ID;
- Published At;
- Reconciliation Required false;
- Last Error to an empty rich-text array.

This avoids stale error text on successfully published/reconciled cards.

## Definite Telegram API failure

Required order:

1. Telegram returns a definite API error.
2. Mark durable delivery `failed`.
3. Set Notion Status `Error`.
4. Set Notion Delivery State `failed`.
5. Store a sanitized Last Error; never store bot tokens, Authorization headers or secrets.
6. Do not retry automatically.

Changing Notion back to `Ready/pending` alone is intentionally insufficient: the durable ledger still blocks the claim.

### Explicit failed retry

Retry is allowed only after operator review and explicit release:

1. Inspect the Telegram failure and correct its cause.
2. Confirm there is no evidence the message was accepted.
3. Call `release_telegram_publication_failed(Publication ID)`.
4. Release must return true exactly once. A second release should return false.
5. Only then restore the Notion card to the approved retry state.
6. Re-run through the normal atomic claim path.

If content/payload changed, assign a new Publication ID rather than reusing the old one.

## Telegram sent, but durable SENT write failed

This is dangerous because Telegram may already contain the message.

1. Set Notion `Error` when reachable.
2. Set Delivery State `uncertain`.
3. Set Reconciliation Required true.
4. Store the captured Telegram Message ID when available.
5. **Do not retry Telegram.**
6. Inspect Make execution, channel state and Supabase evidence.
7. Reconcile durable state manually according to evidence.

A timeout or writeback error is never proof that the Telegram send did not occur.

## Durable Supabase SENT, but Notion Published writeback failed

This state is safer because durable evidence already proves the send:

- Supabase state = `sent`;
- Telegram Message ID is stored durably;
- Notion is `Error / uncertain / Reconciliation Required = true`.

**Never send again.** Recovery is read-only with respect to Telegram.

### Recovery procedure

1. Read `get_telegram_publication_delivery(Publication ID)`.
2. Require all of:
   - returned Publication ID exactly matches the card;
   - state is `sent`;
   - Telegram Message ID is present and > 0.
3. Do not invoke any Telegram module.
4. Convert message ID to a numeric value.
5. Atomically PATCH Notion to:
   - Status `Published`;
   - Delivery State `sent`;
   - Telegram Message ID = durable value;
   - Published At = recovery time (or documented durable delivery time when available);
   - Reconciliation Required false;
   - Last Error cleared using `rich_text: []`.
6. Verify Notion and Supabase agree.

This recovery path has been acceptance-tested with **no Telegram module present**.

## Preflight before enabling a new scheduler

- GitHub CI actually executed and is green.
- Ollama Integration actually executed and is green.
- Jafar Apple actually executed and is green.
- Notion connection healthy.
- Supabase connection healthy.
- Telegram connection healthy (`getMe` and target chat access verified).
- No `uncertain` deliveries.
- No records requiring reconciliation.
- No stale claims.
- Zero unexpected `Ready` cards.
- No test delivery rows.
- v2 and v3 must never both be active.
- v3 must first be tested without a public Telegram send.

A GitHub Actions job with `steps = []` is not a passing or failing code test; treat it as runner/provisioning failure and do not cut over until a real job executes.

## v2 -> v3 cutover

1. Keep v2 live while v3 is built and inspected.
2. Keep v3 inactive.
3. Validate all mappings, filters, connections and branch payloads.
4. Run negative and non-public acceptance tests.
5. Confirm production health snapshot has no blockers.
6. Deactivate v2.
7. Confirm v2 is inactive and has no incomplete execution.
8. Run read-only `getMe` + `getChat(@iznanka_ugolovki)` preflight.
9. Obtain explicit approval for one controlled real Telegram end-to-end test.
10. Run the controlled test through v3.
11. Verify Telegram, Supabase `sent`, Notion `Published`, Telegram Message ID and Published At agree.
12. If and only if all cutover gates pass, leave v3 active as production.

## Rollback

If v3 fails before a Telegram message is accepted:

1. Deactivate v3.
2. Resolve/reconcile all `claimed`, `failed` and `uncertain` records.
3. Only after no ambiguous delivery remains, reactivate the last known-good scheduler if its payload contract is still valid.

Never reactivate v2 while v3 has an unresolved claim or uncertain delivery for the same Publication ID.

If a durable record is already `sent`, rollback must not send that Publication ID again.

## Test-data hygiene

Every controlled acceptance test must be cleaned up after verification:

- test Notion cards return to `Review` (or are archived by the operator);
- Delivery State returns to non-production test-safe state;
- fake Telegram Message IDs and Published At values are removed;
- test hashes/errors are cleared;
- synthetic `test_v3_%` Supabase ledger rows are deleted;
- cleanup is verified before production resumes.

## Weekly editorial analytics

Analytics must use observed data only. Missing metrics stay `None`/unavailable; they are never converted to zero.

The report format is:

`ФАКТ -> ЧТО ЭТО ОЗНАЧАЕТ -> ПОЧЕМУ -> ЧТО ДЕЛАТЬ ДАЛЬШЕ`

Review at minimum: best/weak posts, views, forwards, subscriber growth/churn when available, advertising sources/cost, retention and real client inquiries.
