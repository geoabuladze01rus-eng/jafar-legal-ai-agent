# Telegram command bridge on JAFAR 2.0

This integration is designed for the owner workflow:

`ChatGPT/Codex -> authenticated remote MCP -> immutable Telegram draft -> explicit owner approval -> immediate/scheduled execution -> Telegram Bot API -> persisted status/message_id`

## Safety defaults

The integration is fail-closed by default:

- `TELEGRAM_PRODUCTION_SEND=false`
- `TELEGRAM_DRY_RUN=true`
- outbound destinations must be present in `TELEGRAM_ALLOWED_CHAT_IDS`
- production approval requires `TELEGRAM_OWNER_APPROVER_ID`
- remote MCP requires a strong bearer token, an HTTPS public URL and loopback bind
- scheduled state is persisted in owner-only SQLite files on POSIX
- uncertain Telegram POST delivery is never automatically retried
- Telegram draft payloads are SHA-256 bound before owner approval
- execution accepts only an `approval_id`; replacement text, image, chat or schedule data cannot be supplied after approval
- confidential AI work remains governed by the JAFAR ModelRouter/PrivacyPolicy; Ollama stays local-first for confidential material

## Required environment

Keep secrets only in the local `.env`; never commit them.

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHAT_IDS=...
TELEGRAM_SCHEDULER_ENABLED=true
TELEGRAM_PRODUCTION_SEND=false
TELEGRAM_DRY_RUN=true
TELEGRAM_OWNER_APPROVER_ID=...
TELEGRAM_POLL_IDENTITY_SECRET=...

JAFAR_MCP_TRANSPORT=streamable-http
JAFAR_MCP_HOST=127.0.0.1
JAFAR_MCP_PORT=8000
JAFAR_MCP_AUTH_TOKEN=<random secret of at least 32 characters>
JAFAR_MCP_PUBLIC_URL=https://<private-public-endpoint>
```

For production polling, `TELEGRAM_POLL_IDENTITY_SECRET` must be a non-placeholder secret of at least 32 characters.

## Local readiness sequence

Keep live sending disabled first.

1. Ensure Ollama is running locally and the configured `qwen3:4b` model is available when confidential model work is required.
2. Start the MCP server locally using stdio or streamable HTTP.
3. Call `telegram_status` and verify configuration without exposing secrets.
4. Create a post draft with `telegram_create_post_draft`.
5. Review its destination, schedule and `payload_hash`.
6. Explicitly approve it with `telegram_approve_publication` and confirmation `APPROVE`.
7. Only for the owner-controlled live smoke, switch to `TELEGRAM_PRODUCTION_SEND=true` and `TELEGRAM_DRY_RUN=false`.
8. Execute the already-approved action using `telegram_execute_approved`.
9. Verify `message_id` for immediate sends or `schedule_id` for scheduled sends.
10. Return live flags to the desired operating configuration after the smoke.

## Scheduler

Run the standalone worker when the FastAPI process is not responsible for scheduling:

```bash
python -m jafar.telegram_scheduler_worker
```

The scheduler claims due rows atomically. A second worker cannot claim the same pending row after the first worker changes it to `sending`.

If the process dies while an item is `sending`, startup converts it to `delivery_uncertain`. It is not retried automatically. Use owner-controlled reconciliation with external Telegram evidence.

## Remote MCP

Run the MCP process bound only to loopback:

```bash
JAFAR_MCP_TRANSPORT=streamable-http \
JAFAR_MCP_HOST=127.0.0.1 \
JAFAR_MCP_PORT=8000 \
python -m jafar.telegram_mcp
```

Expose that loopback service only through an HTTPS reverse proxy or secure tunnel. Do not bind the MCP process directly to `0.0.0.0`.

The public endpoint must use HTTPS and clients must authenticate with the configured bearer token. Do not place the token in a URL.

## Natural-language contract

A connected ChatGPT/Codex client should translate natural-language requests into the approval-first tools.

Example:

> Publish this post tomorrow at 09:00 with this image.

Expected tool sequence:

1. `telegram_create_post_draft(...)`
2. show/review the draft metadata and request owner confirmation
3. `telegram_approve_publication(...)`
4. `telegram_execute_approved(...)`
5. return the persisted `schedule_id`
6. after execution, `telegram_get_delivery_status(...)` returns the Telegram `message_id` when known

A client must not call approval merely because it created the draft. Approval is a separate owner decision.

## Full historical channel reading

Old-channel history ingestion is intentionally not required for the publication bridge. Bot API polling handles current allowed updates, not arbitrary historical channel history. Full historical reading should be implemented separately through a read-only MTProto/Telethon adapter with separate credentials and no outbound user-account capability.
