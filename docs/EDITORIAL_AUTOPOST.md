# Djafar editorial autopost

This is the current-main editorial path for the Telegram channel «Уголовка наизнанку».

## Architecture

```text
DeepSeek Harness / POST /v1/editorial/posts
        |
        v
DeepSeek Flash -> structured editorial draft
        |
        v
risk gate: GREEN / YELLOW / RED
        |
        v
GPT Image 2.5 Flare -> clean visual without text
        |
        v
SQLite editorial queue
        |
        +--> owner Telegram preview
        |      [publish] [reject]
        |      [rewrite] [new visual]
        |
        +--> optional GREEN auto-publish
```

The default is approval-first. Automatic channel delivery is impossible unless both
`TELEGRAM_PRODUCTION_SEND=true` and `TELEGRAM_DRY_RUN=false`.

## Editorial safety policy

- Arthur Chernov is described only as a lawyer and former investigator; never as an advocate.
- Current client/case material is RED.
- News, case law, law changes and unverified legal claims are at least YELLOW.
- GREEN is reserved for safe evergreen/editorial material without a current case or unresolved legal claims.
- Generated visuals contain no text, logos, personal data or recognizable real-case participants.
- The model cannot silently turn RED/YELLOW into automatic production delivery.

## Required environment

```dotenv
TELEGRAM_BOT_TOKEN=...
TELEGRAM_POLLING_ENABLED=true

DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_EDITORIAL_MODEL=deepseek-flash

OPENAI_API_KEY=...
EDITORIAL_IMAGE_MODEL=gpt-image-2.5-flare
EDITORIAL_IMAGE_SIZE=1024x1536

EDITORIAL_ENABLED=true
EDITORIAL_OWNER_USER_ID=...
EDITORIAL_OWNER_CHAT_ID=...
EDITORIAL_CHANNEL_ID=...
EDITORIAL_DB_PATH=.jafar/editorial.sqlite3

# Start safely:
TELEGRAM_PRODUCTION_SEND=false
TELEGRAM_DRY_RUN=true
EDITORIAL_AUTO_PUBLISH_GREEN=false
```

Do not commit secrets or personal Telegram IDs.

## Smoke test

With the API running and authenticated, call:

```http
POST /v1/editorial/posts
Content-Type: application/json

{
  "topic": "Почему «просто поговорить» редко означает просто разговор",
  "source_text": "Use only a pre-approved evergreen editorial brief. Do not invent legal citations.",
  "source_urls": [],
  "is_news": false,
  "current_case": false
}
```

Expected result:

1. DeepSeek returns schema-valid JSON.
2. The policy layer classifies risk.
3. GPT Image generates a portrait visual.
4. The draft is persisted in SQLite.
5. The owner receives the image and full draft in the private Telegram review chat.
6. An unauthorized Telegram user cannot execute callback actions.

## Production activation

After a successful preview smoke test:

```dotenv
TELEGRAM_PRODUCTION_SEND=true
TELEGRAM_DRY_RUN=false
```

Keep `EDITORIAL_AUTO_PUBLISH_GREEN=false` initially. This enables the owner approval button
without allowing unattended publication. After real-world verification, GREEN-only automatic
publishing can be enabled separately:

```dotenv
EDITORIAL_AUTO_PUBLISH_GREEN=true
```

YELLOW and RED remain approval-gated.

## Legacy Supabase autopilot

A historical Supabase cron/editorial autopilot may still exist in the project. Do not enable
a second scheduled producer until ownership is explicit. The legacy worker should either be
retired or repointed to the current Djafar editorial endpoint; running both can create duplicate
publication attempts.

The current Python module does not require Make or Notion.
