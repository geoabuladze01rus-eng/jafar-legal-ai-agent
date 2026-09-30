# Telegram v3 deployment history

This file is retained only as a compatibility pointer for older links.

The Make-based v3 candidate described by earlier revisions was not promoted. The
current production runtime is Supabase Cloud:

`Notion → telegram-notion-sync-v3 → telegram_publication_queue → telegram-publisher-v3 → telegram-egress → Telegram`

Make scenario `7305820` is rollback-only and must remain inactive while the Supabase
publisher is enabled. Scenario `7311904` is experimental/off and is not production.

Use [OPERATIONS.md](OPERATIONS.md) for the authoritative topology, safety gates,
delivery semantics, reconciliation and rollback procedure. Use
[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for the release gate.
