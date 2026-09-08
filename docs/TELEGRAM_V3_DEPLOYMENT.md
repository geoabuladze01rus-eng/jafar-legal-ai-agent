# Telegram Scheduler v3 deployment contract

This document pins the production migration contract for Telegram channel `@iznanka_ugolovki`.

## Live / candidate scenarios

- Current live Make scenario: `7305820` — `Telegram @iznanka_ugolovki — Production Scheduler v2 — LIVE`.
- Candidate Make scenario: `7311904` — `Telegram @iznanka_ugolovki — Production Scheduler v3 — OFF`.
- Read-only Telegram preflight: `7311962` — `TEMP — Telegram v3 Read-Only Preflight`.
- Supabase/reconciliation preflight: `7312653` — temporary on-demand scenario, kept OFF outside controlled maintenance windows.

The Make plan currently allows only one active scenario. v2 and v3 must therefore never be active at the same time. Preflight scenarios are executed only inside a controlled maintenance window after v2 is disabled. v2 is restored immediately after each controlled test.

As of the latest acceptance cycle, v2 is LIVE and v3 is OFF.

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

The pre-claim safety gate is attached before SHA-256 and Supabase claim. Future, risky, unverified, incomplete and unapproved cards therefore never create durable ledger claims.

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

All v3 Supabase claim/SENT/FAILED modules use this raw-JSON contract.

## Verified atomic-claim and retry behavior

Controlled Make/Supabase tests proved the following behavior:

1. First `claim_telegram_publication` for a new Publication ID/hash returned `true`.
2. A second claim with the same Publication ID/hash returned `false`.
3. A controlled Telegram failure (`400 Bad Request: chat not found`) executed the failure path in the required order: Telegram failure -> Supabase `failed` -> Notion `Error/failed`.
4. Resetting only the Notion card to `Ready/pending` did not permit another send: durable claim returned `false` and Telegram was not called.
5. First explicit `release_telegram_publication_failed` returned `true`; a second release returned `false`.
6. After explicit release, a new claim was allowed; the controlled Telegram failure again transitioned durable state back to `failed`.
7. All temporary test ledger rows were deleted after verification; cleanup confirmed zero `test_v3_%` residue.

This proves that retry is an explicit operator action rather than a side effect of changing Notion fields.

## Durable SENT and Telegram Message ID contract

`mark_telegram_publication_sent` was tested through Make with a synthetic Telegram Message ID and returned HTTP 204. Supabase stored the expected `sent` state and bigint message ID.

A separate acceptance test found that the standard Notion Make mapper can serialize a numeric-looking mapped value as a JSON string. Notion correctly rejected `Telegram Message ID = "424243"` because the property is numeric.

The fix is explicit numeric normalization before durable SENT/writeback. v3 now contains four `toNumber` modules:

- text: module `42`;
- photo: module `43`;
- poll: module `44`;
- quiz: module `45`.

The resulting Notion writeback was verified with a real number value.

## Atomic Notion Published writeback

The standard `notion:updateADatabaseItem` module does not reliably clear an existing rich-text property when mapped value is an empty string. This was observed with `Last Error` after successful reconciliation.

Production v3 therefore uses `notion:makeApiCall` for the final Published writeback. Each branch performs one authorized PATCH to the page and atomically sets:

- `Status = Published`;
- `Delivery State = sent`;
- numeric `Telegram Message ID`;
- `Published At`;
- `Reconciliation Required = false`;
- `Last Error = { rich_text: [] }`.

Verified atomic writeback modules:

- text: module `46`, error handler `47`;
- photo: module `48`, error handler `49`;
- poll: module `50`, error handler `51`;
- quiz: module `52`, error handler `53`.

A controlled Make execution verified that the raw Notion PATCH clears `Last Error` while preserving Published/sent/message-id state.

If any atomic Published writeback fails after durable Supabase state is already `sent`, the branch writes Notion as `Error / uncertain / Reconciliation Required = true` and explicitly says **DO NOT RETRY TELEGRAM**.

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
  -> toNumber(Telegram Message ID)
  -> Supabase mark sent
  -> atomic Notion Published/sent/message-id/Published At/clear-error
```

Definite Telegram failures transition the durable ledger to `failed` before Notion is written `Error`. Automatic retry is never allowed merely because a Notion field was changed.

If Telegram has returned a message id but durable SENT persistence fails, Notion is written as `Error + uncertain + Reconciliation Required = true`. Automatic retry is forbidden.

If final Notion Published writeback fails after Supabase is already `sent`, the durable `sent` state prevents a duplicate post and the card enters reconciliation.

## Reconciliation acceptance test

The dangerous state `Supabase = sent` while Notion Published writeback failed was reproduced without sending to Telegram:

1. A synthetic delivery was atomically claimed and marked `sent` in Supabase with message id `424245`.
2. The Notion Published writeback was intentionally made invalid.
3. Durable Supabase state remained `sent`.
4. Notion became `Error / uncertain / Reconciliation Required = true` with an explicit no-retry warning.
5. A recovery scenario then called only `get_telegram_publication_delivery` and received the durable `sent` state and message ID.
6. Recovery executed `Supabase read -> extract -> toNumber -> Notion Published` with **no Telegram module present**.
7. Notion was restored to Published/sent with the durable message ID and reconciliation cleared.
8. The test Notion item was reset to `Review/pending` and all synthetic delivery fields were removed.
9. All `test_v3_%` Supabase rows were deleted; cleanup confirmed zero residue.

This proves that reconciliation can repair Notion from durable evidence without a duplicate Telegram send.

## Telegram preflight verification

Controlled read-only Make preflight succeeded:

- `getMe` returned HTTP 200 for bot `@Djafar23_bot`;
- `getChat(@iznanka_ugolovki)` returned HTTP 200 for the target channel.

No Telegram message was sent.

## Negative acceptance tests

Two Ready-like test cards were tested while v2 was disabled:

- `Fact Check Status = unverified` was blocked before SHA/Supabase/Telegram;
- a future Publish Date was blocked before SHA/Supabase/Telegram.

A fully valid test card was also passed through `safety gate -> Publication ID extraction -> SHA-256 -> atomic claim -> Notion claimed` while Telegram was physically blocked before the router. The test was then cleaned up.

## Latest v3 empty-queue smoke test

After the atomic Published writeback migration, controlled Make execution `725eee2494194085a623768b81934918` completed successfully.

Only these modules executed:

1. BasicTrigger
2. Notion search
3. Publish Date calculation

No SHA-256, Supabase claim, Notion claim or Telegram module ran because the queue was empty. v3 was then disabled and v2 restored LIVE.

## Quiz contract

v3 uses the current Telegram Bot API field `correct_option_ids` from Notion `Correct Option IDs JSON`.
The legacy `Correct Option ID` remains migration-only and must not drive v3 delivery.

## GitHub Actions blocker

On branch head `c7aa6d6e9e0f52d2b654f0101a9689fb51456aea`, CI, Ollama Integration and Jafar Apple all completed with failure while their jobs reported `steps = []`. No test/build step actually executed. A prior branch head had CI/Ollama/Apple green.

Treat this as runner/provisioning failure, not evidence of a code regression. A newer head must still receive real runners and pass before cutover.

## Cutover gate

Do not enable v3 as production until all of these are true:

- latest code head has actually executed and passed CI/Ollama/Apple;
- Notion queue has no unexpected Ready/In progress/uncertain records;
- no durable ledger record needs reconciliation;
- v2 is disabled in the controlled cutover window;
- read-only `getMe` and `getChat(@iznanka_ugolovki)` preflight passes;
- v3 acceptance tests pass without a public duplicate;
- one explicitly approved controlled real Telegram end-to-end test succeeds;
- only then v3 is activated.
