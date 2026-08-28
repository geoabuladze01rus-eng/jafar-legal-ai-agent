# ЮСТИЦИЯ AI

**Интеллектуальная система адвоката**

`JAFAR` remains the internal technical codename for the legal-intelligence engine and repository architecture. The external product identity approved for release is **ЮСТИЦИЯ AI**.

## Core product boundary

ЮСТИЦИЯ AI is a lawyer-controlled legal intelligence system for document analysis, evidence/provenance review, deadlines, legal research, multi-model verification, drafting assistance, voice workflows and controlled external actions.

The product is designed around four layers:

1. Evidence
2. Legal Intelligence
3. Lawyer Decision
4. Controlled Execution

No model output becomes a fact solely because a model produced it. Mutating or external legal actions require explicit human approval and auditability.

## Cost & scale

Commercial release must keep JAFAR Cost & Scale Control enabled: token metering, configurable provider pricing, spend budgets, atomic spend reservation, provider kill switches, bounded queues, rate limiting, retry/fallback controls and safe reusable caching.

## Telegram MCP

Telegram publishing is integrated as a controlled external-action surface. Configuration is intentionally fail-closed:

- `TELEGRAM_ALLOWED_CHAT_IDS` is mandatory for outbound delivery; the allowlist is rechecked at actual delivery time and when poll results are read.
- A bot token alone never enables live publishing. Live sends require both `TELEGRAM_PRODUCTION_SEND=true` and `TELEGRAM_DRY_RUN=false`.
- `TELEGRAM_SCHEDULER_ENABLED=false` by default. The SQLite scheduler records idempotency, delivery state and restart uncertainty; an interrupted `sending` item is not replayed automatically.
- Scheduled content is stored in the local scheduler database, which is restricted to the owner on POSIX hosts. Do not place that database in shared/cloud-synced folders.
- Local MCP uses `stdio`. Remote `streamable-http` must bind to loopback, use a strong bearer token, advertise an HTTPS public URL and be exposed only through an authenticated HTTPS proxy/tunnel.
- OAuth-oriented UI clients should use an OAuth-capable access proxy rather than treating the private static bearer mode as a full authorization server.
- Telegram transport exceptions and scheduler errors are sanitized so bot-token URLs, prompts and legal content are not written into persistent error fields.

Minimal local configuration:

```dotenv
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHAT_IDS=-1001234567890
TELEGRAM_PRODUCTION_SEND=false
TELEGRAM_DRY_RUN=true
TELEGRAM_SCHEDULER_ENABLED=false
TELEGRAM_SCHEDULER_DB_PATH=var/telegram_scheduler.sqlite3
JAFAR_MCP_TRANSPORT=stdio
```

For a remote private endpoint additionally configure `JAFAR_MCP_AUTH_TOKEN`, `JAFAR_MCP_PUBLIC_URL=https://...`, keep `JAFAR_MCP_HOST=127.0.0.1`, and terminate TLS/authentication at the external access proxy.
