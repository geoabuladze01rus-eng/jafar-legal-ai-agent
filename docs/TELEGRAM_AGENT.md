# Telegram editorial agent

## Goal

Automate the editorial operations of the Telegram channel while keeping consequential legal communications behind a human approval gate.

## First release

- Telegram Bot API client.
- Channel health check (`getMe` / `getChat`).
- Scheduled publication queue (application-owned; persistence will be added next).
- Poll creation.
- Webhook endpoint for incoming Telegram updates.
- Comment classification and moderation pipeline.
- Editorial approval queue for sensitive posts and potential client messages.
- Audit log for every outbound action.

## Automation policy

### Automatic

- Scheduled posts that have already been approved.
- Pre-approved polls.
- Low-risk moderation such as obvious spam.
- Routine channel health checks.

### Human approval required

- Individual legal questions that could be construed as advice.
- Potential client situations.
- Allegations against identifiable people or organizations.
- Sensitive criminal cases.
- Personal or confidential information.
- Unverified claims.

## Secrets

Never commit the Telegram bot token. Store it in the deployment secret store or `.env` locally. The repository must contain only variable names and safe defaults.

## Deployment sequence

1. Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHANNEL_ID` to the runtime environment.
2. Verify the bot with `getMe`.
3. Verify channel access with `getChat`.
4. Configure a webhook on a public HTTPS endpoint with a secret token.
5. Enable the publication queue only after the webhook and audit log are healthy.
6. Start with approval-required mode; only promote low-risk, pre-approved content to automatic publishing.
