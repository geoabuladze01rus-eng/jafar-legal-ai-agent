# Jafar Private Beta 0.8 plan

## Current state

Jafar 0.7 has a local backend, read-only Gmail gateway, approval-gated outbound
drafts, and deterministic local analysis fallback. The canonical Supabase project
is `pzizksezplntcdatdwvf`; schema-only export remains blocked until the owner
completes `supabase login`. No remote migration or write is permitted.

## Distribution gap

The current developer build depends on a repository checkout and `.venv`, so it
cannot run on a clean Mac without Python, the repository, and developer tools.
For 0.8, use a signed helper executable bundled in the app (Option B): it is
smaller and easier to notarize than an embedded interpreter, while preserving a
clear update and rollback boundary. A packaged Python runtime remains a fallback
if native dependencies prevent a helper build.

Release requirements: Release scheme, stable bundle identifier/version, hardened
runtime, least-privilege entitlements, Developer ID signing, notarization,
Gatekeeper verification, and a signed DMG. Do not sign or notarize without owner
credentials.

## Diagnostics and observability

`GET /health` is liveness-only; `GET /readiness` reports safe component statuses
without tokens, email addresses, document names, or message bodies. Local JSON
logging uses severity/component/timestamp fields and conservative redaction. Add
rotation and bounded retention before cohort distribution; no remote telemetry.

## Privacy onboarding

The first-run flow must state that Jafar is an assistant, not an autonomous
lawyer; legal output requires human verification; outbound mail/Telegram and
filings require explicit confirmation and are not automatic; Gmail/Outlook access
is read-only; external AI is opt-in and may send selected text off-device; and
confidentiality remains the lawyer's responsibility.

## Cohort checklist

- signed installer tested on a clean Mac;
- local Keychain and Gmail OAuth setup verified;
- tenant/account isolation and RLS acceptance tests pass;
- crash logs expose only a request/error ID;
- support runbook and rollback package available;
- no live client documents used in acceptance tests.

## Commercial MVP gaps

Canonical Supabase baseline, signed distribution, first-run onboarding, support
workflow, tenant isolation evidence, and a repeatable upgrade/rollback channel
remain prerequisites. This document does not change Supabase status to PASS.
