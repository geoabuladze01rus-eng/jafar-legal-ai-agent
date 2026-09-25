# JAFAR Telegram Cloud Production Readiness

## Current architecture

Supabase Cloud is the 24/7 production runtime. The canonical chain is:

`Notion Ready → sync v3 → durable queue → publisher v3 → final Notion guard → atomic claim → restricted egress → Telegram → durable sent/message_id → Notion Published`

Make v2 (`7305820`) is rollback-only/inactive. The MacBook and GitHub Actions are not
runtime dependencies.

## Completed

- Text, approved-photo, poll and quiz publication contracts.
- Human-controlled `Review → Ready`; AI models have no Ready field.
- Final live Notion revalidation immediately before claim.
- Restart-safe Supabase queue and idempotency ledger.
- Restricted service-role Telegram egress and allowlisted destinations.
- Read-only production-health evaluation for both cron jobs and delivery state.
- Retired bot-access probe returns HTTP 410.

## Safety gates

Only `Platform=Telegram`, `Status=Ready`, due publications with a valid lowercase
SHA-256 fingerprint, `Fact Check Status=verified|not_required`, low legal/privacy
risk, no current-case risk, no editorial blockers, `pending` delivery, no message ID
and no reconciliation flag may be claimed. AI drafts remain `Review` and identify
Артур Чернов as a юрист and former investigator, never as an advocate.

## Telegram delivery

Egress exposes only `sendMessage`, `sendPhoto` and `sendPoll`. The production channel
is checked against the egress allowlist at actual delivery. The bot token is obtained
only through a service-role-only Vault/RPC boundary and is neither logged nor returned.

## Visual delivery

Photo delivery requires a versioned `Visual Asset Key` plus matching category. The
resolver accepts only an approved, active asset with lowercase SHA-256 and non-empty
Base64. Publisher and egress enforce image MIME/size limits. Legacy Drive IDs and
photo URLs are not the canonical production asset source; required photos never fall
back to text.

## Notion sync

Sync queries Telegram cards in `Ready` only and repeats safety checks before upsert.
It cannot overwrite claimed, sent, failed or uncertain queue state. After delivery,
durable Supabase state is authoritative; a Notion writeback failure schedules only a
Notion repair and never a Telegram resend.

## Idempotency

The atomic claim binds Publication ID to a hash of chat ID, type, content, caption,
visual key/category/SHA-256, poll question/options/correct IDs and explanation.
Claimed, sent and uncertain records cannot be automatically reclaimed. A definite
pre-send failed record requires an explicit operator release.

## Security

- `telegram-egress` has platform JWT verification plus exact service-role Bearer.
- Publisher/sync cron endpoints use a separate constant-time worker-secret boundary.
- Tables and secret getter RPCs are denied to public/anon/authenticated roles.
- Error responses expose only bounded error codes/types, not tokens or post bodies.
- No generic Telegram Bot API proxy exists.

## Monitoring

The read-only health snapshot covers cloud publisher/sync enabled and dry-run flags,
token presence, both cron active/fresh/last status, due/claimed/stale/uncertain/failed
counts, reconciliation count and Make v2 inactivity. `uncertain`, stale claims,
reconciliation work or an active Make sender are hard blockers.

## Rollback

Set `telegram_publisher_config.enabled=false` first. Reconcile and confirm zero
claimed, uncertain and reconciliation-required records and understand the due queue.
Only then may Make v2 be activated. Never operate both senders simultaneously.

## Tests

The local Python suite covers the publication policy, AI Review boundary, identity,
Notion round-trip, durable states, unknown-state fail-closed behavior, Supabase SQL
permissions and Edge Function production contracts. CI must never perform a real
Telegram send.

## External infrastructure limitations

GitHub Actions runner or billing availability may currently prevent hosted jobs from
starting (`runner_id=0`, `steps=[]`). That is an external CI gate and must not be
reported as green. It is not a production runtime dependency and does not interrupt
Supabase publication. A merge still requires a real hosted runner execution or an
explicit owner decision under the repository release policy.

The first naturally scheduled, owner-approved Supabase delivery should be observed
for matching Telegram message ID, durable `sent`, and Notion `Published`. Do not
create a public test post solely to satisfy this observation.
