# macOS desktop backend runtime map

| Area | Desktop beta treatment |
| --- | --- |
| Entrypoint | `jafar.desktop_sidecar` starts Uvicorn with `jafar.main:app`. |
| HTTP API | FastAPI `/health` plus authenticated `/v1/*`; bind is fixed to `127.0.0.1`. |
| Required runtime | Python 3.12, FastAPI/Uvicorn, Pydantic, HTTPX, document parsers, crypto/TLS trust store. |
| Matter/document workflow | Required local baseline; uses the existing in-memory repository and never auto-persists case conclusions. |
| Ollama | Optional local feature at `127.0.0.1:11434`; qwen3:4b remains the default local model. |
| OpenAI | Optional external service, absent from sidecar environment and confidential cloud fallback forced off. |
| Supabase / pgvector | Production/external service; not supplied to desktop sidecar and not required to launch. |
| Google OAuth, Gmail, Calendar | Optional external integrations; no credentials are inherited and OAuth is not a launch dependency. |
| Telegram | Production-only outbound runtime; polling and production sending are forced off. |
| Filesystem | Immutable code in bundle; app support, logs, cache and temp state belong under `~/Library/*/JAFAR`. |
| Logging | Uvicorn warning level only; Swift discards sidecar stdout/stderr in normal UX.  Tokens, document bodies and deployment secrets are never intentionally logged. |
| Shutdown | Swift terminates its child; sidecar also monitors the exact parent PID and exits if that parent vanishes. |

The bundled one-folder runtime deliberately excludes source checkout metadata, tests,
documents, `.env`, developer virtualenvs, local caches and signing material.  Its
manifest records only runtime component hashes.  Local persistence beyond the
existing in-memory desktop baseline needs a separate encrypted-storage design; it
must not reuse production Supabase service credentials in a customer app.
