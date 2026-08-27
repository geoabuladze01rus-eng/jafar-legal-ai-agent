# Jafar Private Beta 0.7 — Release Freeze

Date: 2026-08-27
Branch: `release/jafar-private-beta-0.7`

## Scope

This branch freezes the current Private Beta line after the verified Apple local-backend autostart work and the Gmail read-only gateway implementation.

## Verified baseline inherited from the Beta line

- legal analysis core and matter lifecycle
- PDF/DOCX/TXT/Markdown ingestion with provenance
- Pavlik acceptance/evidence-gap contracts
- fail-closed API-key boundary for `/v1/*`
- Apple macOS/iOS client build path
- macOS local backend autostart
- ephemeral API key handling via Keychain
- typed and voice command paths through the same backend client
- spoken `Джафар на связи` smoke path
- Outlook read-only orchestration already present in the canonical Beta line
- Gmail read-only gateway with local OAuth Desktop flow and exact `gmail.readonly` scope

## Current verification snapshot

From the Gmail gateway branch used as this release base:

- Ruff: PASS
- pytest: 211 passed, 1 known non-blocking warning
- synthetic Gmail HTTP command E2E: PASS
- installed wheel import: PASS
- macOS Keychain backend: PASS
- macOS `JafarApp_macOS` Debug build with signing disabled: PASS

## Safety boundaries

Private Beta 0.7 is intentionally review-first.

- no Gmail send/draft-create/modify/archive/trash/delete
- no automatic download of external large files
- external links and attachment metadata may be detected, but are not opened or fetched automatically
- no automatic filing, legal submission, Telegram legal reply, or consequential outbound action
- no production deployment
- no production Supabase changes
- no secrets, OAuth tokens, API keys, client PDFs, mailbox bodies, or private legal materials committed
- external AI remains explicit opt-in where applicable

## Remaining release gate

The principal unresolved acceptance gate is a **live Gmail OAuth test on the owner Mac** using a Google OAuth Desktop client created by the owner.

Required live scenario:

1. authorize Jafar with Google using `gmail.readonly` only;
2. launch Jafar normally;
3. issue `Разбери последнее юридическое письмо` by voice;
4. confirm Jafar reads the mailbox, identifies the latest relevant legal email, returns a bounded summary and places it in current lawyer context;
5. confirm no mutation of Gmail state and no attachment bytes are fetched automatically;
6. quit Jafar and confirm local backend/token cleanup behaves as designed.

Until this live Gmail gate passes, this branch is a release candidate for Private Beta, not a general-production release.

## Release readiness estimate

- owner-local Private Beta: high confidence, pending live Gmail OAuth acceptance
- small trusted lawyer cohort: near-ready after Gmail live gate and packaging/onboarding cleanup
- commercial/public production: not yet ready; installer/notarization/update channel, production observability, privacy onboarding, persistent operational storage and broader integration hardening remain
