# Local Gmail read-only gateway — Private Beta

## Status

The first local Gmail vertical slice is implemented with a safe OAuth setup gate.
Synthetic end-to-end coverage exercises the real command runtime and HTTP endpoint without
using a Gmail account or Google credentials. Live OAuth is enabled only after the owner creates
a Google OAuth **Desktop app** client and completes local consent.

Verified locally on macOS through 2026-08-27:

- Ruff: **PASS**;
- full Python suite: **216 passed, 1 known warning**;
- synthetic Gmail HTTP command E2E: **PASS**;
- Keychain backend resolution: **macOS Keychain**;
- macOS Xcode build: **PASS**;
- live OAuth setup with exact `gmail.readonly`: **PASS** on 2026-08-27;
- live Keychain -> Gmail list/get -> legal triage -> current-context path: **PASS**;
- mailbox mutation, attachment download, and external-link opening during the live check: **none**;
- final command from the macOS app UI through the auto-started loopback backend: **PASS**.

This work does not use Supabase, production infrastructure, deployment, or a paid service.

## Safety boundary

- OAuth requests exactly `https://www.googleapis.com/auth/gmail.readonly`.
- Desktop-client and saved-token configuration must use Google's expected authorization/token
  endpoints and a loopback-only redirect; missing or unexpected scope reports fail closed.
- The application exposes only Gmail `messages.list` and `messages.get` operations.
- There is no send, draft-create, modify, label, archive, trash, delete, or attachment-get method.
- OAuth credentials are stored in the local protected keychain under
  `ru.jafar.legal-ai.gmail-oauth`; no repository token file is created.
- The live API partial-response fields exclude MIME body data; triage uses the bounded Gmail snippet.
- Attachment names, media types, and sizes are detected, but attachment bytes are not fetched.
- External HTTP(S) links are detected and returned as metadata, but never opened; query strings
  and fragments are stripped so signed/tracking values do not enter the current context.
- A reply is never sent. The existing reply command remains review-only and has no Gmail send path.
- Provider/OAuth response bodies are not returned to the command surface.

Google documents `gmail.readonly` as a restricted read scope. This local single-user Beta keeps
the data and tokens on the user's Mac. Any future multi-user or server-side distribution needs a
fresh Google policy and verification review before it is enabled.

## One-time Google Cloud setup gate

Do not put the downloaded client JSON inside this repository. The repository ignores common
credential filenames as a second line of defense.

1. Create or select a dedicated Google Cloud project and enable the **Gmail API**.
2. In **Google Auth Platform**, configure the app:
   - use **Internal** only when the account belongs to the same Google Workspace organization;
   - otherwise use **External / Testing** and add only the Gmail owner as a test user;
   - add only the `.../auth/gmail.readonly` data-access scope.
3. In **Google Auth Platform → Clients**, create **Application type → Desktop app** and download
   the JSON once.

Google's Gmail Python quickstart lists a Google Cloud project and Gmail account as prerequisites,
not a paid billing account. Do not attach billing for this Beta. If the console unexpectedly asks
for billing or a card, stop rather than accepting it.

Testing-mode grants for an External app can expire after seven days. Re-run the local setup when
Google requires consent again; do not broaden the scope to avoid that control.

## Store the grant in Keychain

After the Desktop app JSON is downloaded outside the repository:

```bash
source .venv/bin/activate
python3 scripts/gmail_oauth_setup.py \
  --client-secrets /absolute/path/outside/repository/client_secret_desktop.json
```

The script opens the system browser on a loopback installed-app flow, requests offline access for
the one read-only scope, and writes the returned credential bundle directly to the local keychain.
It does not print token or client values. After `GMAIL OAUTH SETUP: PASS`, delete the downloaded
JSON through Finder/Trash when it is no longer needed.

If the JSON is missing, is a Web application client, grants an unexpected scope, returns no refresh
token, or Keychain is unavailable, setup stops safely and nothing is saved.

## Command behavior

With the loopback backend running, the existing command works unchanged:

> Разбери последнее юридическое письмо

Jafar lists up to 20 newest Inbox messages, reads their bounded snippet/metadata newest-first,
applies deterministic local legal triage, and stops at the newest relevant message. The response
includes sender, subject, received time, a short summary, attachment metadata, and external-link
metadata when present in that bounded source. That safe
snapshot becomes `LawyerContext.latest_legal_email`, so a following attention/context command can
use it during the same backend session.

If no keychain grant exists, the command returns `setup_required=true` with an actionable message.
If no relevant message is found, it reports that result without changing the mailbox.

## Offline acceptance gate

These checks require no Google account, client JSON, live token, Supabase, or external AI:

```bash
python3 -m ruff check src tests scripts
python3 -m pytest -q tests/test_gmail_auth.py tests/test_gmail_gateway.py
python3 -m pytest -q
```

The synthetic Gmail fixture includes a newer non-legal email, a later legal match, an external
link, and a 50 MiB remote PDF. PASS requires the legal email to be selected while the link remains
unopened, the PDF remains undownloaded, and `mailbox_mutation_performed` remains `false`.

## Live acceptance gate (after credentials exist)

The complete live acceptance gate passed on 2026-08-27, including the user-visible macOS app
round trip. The response was verified without copying private message content into logs or Git.

1. Start the loopback-only backend from the configured branch/worktree.
2. Send `Разбери последнее юридическое письмо` from the macOS app.
3. Confirm the response describes the intended legal message and detected material.
4. Confirm Gmail shows no sent message, changed label, archive, trash, or deletion.
5. Stop the loopback backend after the check.

Observed result: steps 1–5 **PASS**. No send, mailbox mutation, attachment download, or
external-link opening occurred.

Do not paste the OAuth JSON, client ID, client secret, access token, refresh token, message body,
message ID, or attachment bytes into a terminal transcript, issue, commit, or pull request.

## References

- [Google OAuth 2.0 for desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
- [Gmail OAuth scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Gmail API method reference](https://developers.google.com/workspace/gmail/api/reference/rest)
