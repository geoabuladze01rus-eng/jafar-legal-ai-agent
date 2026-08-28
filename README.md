# Jafar — AI Legal Agent

Private AI assistant for legal practice: document analysis, email triage, drafting, deadlines, voice workflows and controlled automation.

## Current foundation

- FastAPI service with `/health` and `/v1/analyze` endpoints.
- Typed legal domain primitives for criminal, arbitration, civil and administrative work.
- Architecture and security boundaries documented in `docs/ARCHITECTURE.md`.
- Environment template without credentials.
- API smoke tests.

## Local start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn jafar.main:app --reload
```

Health check: `GET http://127.0.0.1:8000/health`

## Telegram MCP publishing

Copy `.env.example` to `.env`, set `TELEGRAM_BOT_TOKEN` locally, and set the exact numeric
channel/group IDs in `TELEGRAM_ALLOWED_CHAT_IDS`. The allowlist is checked when a post is
scheduled and again immediately before every Bot API delivery.

Install and inspect local stdio tools:

```bash
pip install -e '.[dev]'
npx @modelcontextprotocol/inspector python -m jafar.telegram_mcp
```

In Inspector, call `telegram_publish_post` for an immediate text post:

```json
{"chat_id":"-1001234567890","text":"Тестовый пост"}
```

For an image use `photo_url` or `photo_base64` (PNG/JPEG/WebP, maximum 10 MB). A long
caption is delivered as the photo followed by complete 4096-character text messages.

Schedule a post using an explicit time zone; the SQLite database survives Mac/process restarts:

```json
{"chat_id":"-1001234567890","text":"Пост на завтра","scheduled_for":"2026-08-30T09:00:00+03:00","idempotency_key":"morning-post-2026-08-30"}
```

Run the scheduler either in the FastAPI service with `TELEGRAM_SCHEDULER_ENABLED=true`, or,
when using the standalone MCP server, under launchd/systemd/Docker restart policy:

```bash
python -m jafar.telegram_scheduler_worker
```

Create a poll and later inspect its stored results:

```json
{"chat_id":"-1001234567890","question":"Какая тема следующего поста?","options":["Ошибки следствия","Работа адвоката","Истории из практики"]}
```

Call `telegram_get_poll_results` with the returned `poll_id`. Enable
`TELEGRAM_POLLING_ENABLED=true` so poll and poll_answer updates are collected. Telegram only
provides per-user answer updates for non-anonymous polls; aggregate poll counts are stored for all polls.

### Remote ChatGPT/Codex MCP

The remote server uses the supported streamable-HTTP transport. Keep it bound to loopback,
terminate HTTPS and authenticate in a reverse proxy or access gateway (Cloudflare Tunnel + Access
is a low-cost MVP choice), and never put either token in the tunnel URL. Set a long random
`JAFAR_MCP_AUTH_TOKEN` and `JAFAR_MCP_PUBLIC_URL=https://your-host.example/mcp`; the server then
also requires `Authorization: Bearer …` at the MCP endpoint. Start it with:

```bash
JAFAR_MCP_TRANSPORT=streamable-http JAFAR_MCP_HOST=127.0.0.1 JAFAR_MCP_PORT=8000 python -m jafar.telegram_mcp
```

Run the scheduler worker alongside it. Configure the HTTPS MCP URL and matching bearer header in
the remote MCP client/Responses API. For ChatGPT/Codex UI connections that require OAuth rather
than custom headers, put the endpoint behind an OAuth-capable access proxy; the static bearer mode
is intended for private API/Codex configurations. OpenAI's remote-MCP API accepts a server URL and
optional request headers for authentication ([API reference](https://platform.openai.com/docs/api-reference/responses-streaming/response/mcp_call_arguments)).

## Roadmap

1. Model provider and structured legal-analysis pipeline.
2. Document/OCR ingestion and persistent matter storage.
3. Gmail/Google Drive/calendar connectors.
4. Apple voice/client layer for Mac, iPhone and iPad.
5. Telegram workflow with approval gates.
6. Production security, audit log, observability and deployment.

## Security rule

No credentials, tokens, private documents or client secrets belong in Git. Consequential external actions require explicit approval.
