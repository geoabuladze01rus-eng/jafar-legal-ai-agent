# Connected Apple dashboard

The iOS/macOS shell is no longer a disconnected voice prototype. It can consume a read-only legal-practice dashboard from the Jafar FastAPI backend.

## Backend contract

`GET /v1/dashboard` returns:

- total and active matter counts;
- overdue deadline count;
- deadlines due within seven days;
- pending approval count;
- matter summaries with the next dated deadline;
- prioritized dashboard signals.

The current dashboard derives deadline signals from the same `MatterRepository` used by the command/document workflows. It does not perform legal actions or mutate a matter.

When `API_KEY` is configured, all `/v1/*` endpoints require:

```text
Authorization: Bearer <API_KEY>
```

`/health` remains available as a non-confidential service probe.

## Apple connection settings

The app exposes connection settings from the top status strip.

- backend URL is stored in UserDefaults;
- API token is stored in Apple Keychain as a generic password;
- the API token is never written to UserDefaults;
- production URLs must use HTTPS;
- plain HTTP is accepted only for localhost / loopback development;
- selecting local mode explicitly overrides environment or bundle defaults.

A connection-test button calls `/v1/dashboard` with the entered URL and token before the user saves the configuration.

## Live interface

`ConnectedRootView` displays:

- connection state (`local`, `connected`, `unavailable`);
- active matter count;
- overdue deadline count;
- seven-day deadline count;
- pending approval count;
- the highest-priority backend signal.

The dedicated `LiveDashboardView` displays the full matter list and the highest-priority signals. Backend signals are also broadcast into the existing `Сигналы и одобрения` center in `ContentView`.

## Safety boundary

The connected dashboard is read-only. A warning, deadline, doctrine impact or pending approval being visible in the UI does **not** authorize Jafar to:

- file or send a legal document;
- alter a legal position;
- apply a redraft;
- approve an external action;
- send email, Telegram or calendar changes.

Those actions remain behind their dedicated human-approval and audit gates.

## Release gate

The connected Apple layer is not considered release-ready until GitHub Actions actually creates jobs and passes:

- Ruff;
- Python compileall;
- pytest;
- iOS simulator build;
- macOS build.

A `startup_failure` with zero jobs is infrastructure failure, not a green result.
