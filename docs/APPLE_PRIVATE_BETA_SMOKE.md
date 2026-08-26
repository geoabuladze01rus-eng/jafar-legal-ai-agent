# Apple private-Beta smoke gate

This gate validates the real Apple client against the local FastAPI `/v1/command` endpoint without committing any secret or client data.

## Preconditions

- `.venv` active;
- Python/Ruff gate green;
- Xcode and XcodeGen installed;
- iOS Simulator and macOS build gates green.

## Start a loopback-only backend

From the repository root:

```bash
python3 scripts/private_beta_backend_smoke.py --hold
```

The helper:

1. chooses a free loopback port;
2. generates an ephemeral API key in memory;
3. starts Jafar in `staging` mode with external AI and Telegram polling disabled;
4. verifies `/health`;
5. verifies authenticated `/v1/command` with `проверка связи`;
6. prints `APPLE_ENDPOINT` and `EPHEMERAL_API_KEY` for the manual Apple client check;
7. writes neither value to Git or a repository file.

Leave this terminal running until the Apple check is complete.

## macOS client check

Generate/build the app from `apple/` if needed, then launch the macOS build. In the app:

1. enter the printed `APPLE_ENDPOINT`;
2. enter the printed `EPHEMERAL_API_KEY`;
3. choose **Сохранить подключение**;
4. leave the prefilled text command `проверка связи`;
5. choose **Отправить команду**.

PASS means the app displays the backend response and no HTTP/auth error.

The API key is stored by the app in device-only Keychain. The smoke helper key is intentionally short-lived; stop the helper with `Ctrl-C` after the check.

## Safety

- backend binds only to `127.0.0.1`;
- no external AI call is enabled;
- Telegram polling is disabled;
- no production database write is part of this gate;
- no client document or mailbox content is required;
- no secret may be committed.

## iOS follow-up

`127.0.0.1` on an iPhone points to the iPhone itself, not the Mac. An iPhone-to-Mac smoke test must use the Mac's LAN address and requires local-network permission. The app plist declares local-network usage for this Beta path. Keep that test on a trusted private network only.

## Gmail command follow-up

The ordinary health smoke remains credential-free. Gmail has an additional safe gate:

- offline/synthetic command E2E must pass before any live authorization;
- live testing starts only after the owner creates a Google OAuth **Desktop app** client;
- the OAuth bundle lives in local Keychain and must never be pasted into app fields or logs;
- the macOS command is `Разбери последнее юридическое письмо`;
- PASS requires a summary plus detected attachment/link metadata with no download, open, send,
  label change, archive, trash, or delete action.

See [`GMAIL_READONLY_PRIVATE_BETA.md`](GMAIL_READONLY_PRIVATE_BETA.md). If the command returns
`setup_required=true`, that is the expected safe stop, not a backend or voice failure.
