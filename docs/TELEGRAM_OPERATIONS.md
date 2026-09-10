# Telegram operations compatibility notice

This legacy filename is retained for existing links. It previously described the
Make v2/v3 cutover and is no longer the source of truth.

Production now runs on Supabase Cloud. Make scenario `7305820` is rollback-only and
inactive; Make v3 `7311904` is experimental/off. Never enable a Make sender while the
Supabase publisher is active.

Use [OPERATIONS.md](OPERATIONS.md) for the current runbook and
[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for the release checklist.
