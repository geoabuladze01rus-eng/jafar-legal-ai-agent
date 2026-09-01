# Google OAuth foundation

This integration prepares Jafar to connect to Google Workspace without committing OAuth credentials or tokens to Git.

## Google Cloud client

Use the existing OAuth 2.0 Web application client `Jafar Legal AI Web`.

Create a new Client Secret if the original full secret is no longer available. Do not delete the old secret until the new connection has been tested successfully.

Add this authorized redirect URI to the Google OAuth client:

```text
http://127.0.0.1:8000/v1/integrations/google/callback
```

The redirect URI configured in Google Cloud must match `GOOGLE_OAUTH_REDIRECT_URI` exactly.

## Local configuration

Create/update `.env` locally. `.env` is already ignored by Git.

```dotenv
GOOGLE_OAUTH_ENABLED=true
GOOGLE_OAUTH_CLIENT_ID=<full client id>
GOOGLE_OAUTH_CLIENT_SECRET=<new full client secret>
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/v1/integrations/google/callback
GOOGLE_OAUTH_PROMPT=consent
GOOGLE_OAUTH_SCOPES="openid email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/calendar.readonly"
```

Never paste real credentials into source files, GitHub issues, pull requests, screenshots, or chat messages.

## Why these scopes

The first integration is read-only:

- Gmail: read messages and settings;
- Drive: read files;
- Calendar: read calendars and events;
- `openid email profile`: identify the Google account that granted access.

No send, delete, modify, move, sharing, or calendar-write scope is requested in this foundation.

## Smoke test

Start Jafar locally:

```bash
uvicorn jafar.main:app --reload
```

Check configuration status:

```bash
curl http://127.0.0.1:8000/v1/integrations/google/status
```

Request an authorization URL:

```bash
curl http://127.0.0.1:8000/v1/integrations/google/authorize
```

Open the returned `authorization_url` in the browser and authorize the configured Google test account. Google redirects back to Jafar's callback endpoint.

A successful callback returns only:

```json
{
  "connected": true,
  "refresh_token_received": true
}
```

The API never returns the Client Secret, access token, or refresh token.

## Current security boundary

This PR intentionally keeps OAuth tokens only in process memory. They disappear when Jafar restarts. This is sufficient for the first local smoke test and prevents premature storage of refresh tokens.

Before production use, add an encrypted credential store with explicit token rotation/revocation handling. Do not store refresh tokens in plaintext application tables.
