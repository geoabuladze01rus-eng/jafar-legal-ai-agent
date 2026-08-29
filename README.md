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

### Editorial autopilot

`TELEGRAM_EDITORIAL_MODE=APPROVE` is the default. `DRAFT` never schedules or publishes;
`APPROVE` needs `telegram_editorial_approve`; `AUTO` approves only low-risk text and high-risk
material still becomes approval-required. This safety gate is not legal clearance.

Create a weekly plan, draft, approve and schedule it in Inspector:

```json
{"week_start":"2026-09-01","topics":["ошибки при допросе","позиция защиты"],"publishing_windows":["09:00","18:00"]}
```

```json
{"item_id":"<planned-item-id>","image_prompt":"restrained editorial cover, blue-black palette"}
```

```json
{"draft_id":"<draft-id>","chat_id":"-1001234567890"}
```

Use `telegram_editorial_safety_check` before review, or create a redacted voice-to-post draft with:

```json
{"transcript":"Эээ, у клиента test@example.com возник вопрос по делу А40-12345/2026"}
```

An image URL/base64 attachment or vendor-neutral `image_prompt` can be stored with a draft. Use
`telegram_editorial_suggest_poll` to propose a poll, then separately approve/schedule it through
the existing poll tools. Use `telegram_editorial_performance`, `telegram_editorial_best_topics`,
and `telegram_editorial_suggest_followup` for locally tracked publication data; unavailable Bot API
views/reactions remain explicitly null rather than invented.

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
