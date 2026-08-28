# Structured model provider

Jafar keeps a deterministic local legal analyzer as the safe fallback and can optionally enrich it with an OpenAI-compatible model provider.

## Configuration

Set these environment variables outside Git:

- `API_KEY` — provider credential.
- `MODEL_PROVIDER` — `openai` or `openai-compatible`.
- `MODEL_NAME` — provider model identifier.
- `MODEL_BASE_URL` — API base URL, defaulting to `https://api.openai.com/v1`.
- `MODEL_TIMEOUT_SECONDS` — network timeout, default `30`.

When `API_KEY` is absent, Jafar never makes a model network call and uses the deterministic analyzer.

## Safety contract

The model receives the document text and task/matter type and must return structured JSON. The response is validated against Jafar's Pydantic models. Malformed, unavailable, or timed-out model responses are discarded and the deterministic result is returned.

This is an analysis/enrichment layer, not an authorization layer: consequential actions such as sending messages, changing matters, creating deadlines, or publishing content remain behind explicit application controls.
## OpenAI Responses API (offline acceptance)

The OpenAI adapter uses `POST /v1/responses` with `model` and structured `input` messages. It reads the SDK-compatible `output_text` field (and safely handles equivalent output content blocks). The adapter exposes diagnostics without logging credentials, prompts, or response bodies. Offline tests cover valid and malformed responses plus authentication, quota, rate-limit, model, request, provider, timeout, and network failures.

The live smoke script is dry-run by default. A second synthetic smoke remains gated until the existing key is connected locally and an explicit opt-in is authorized; no live request was made during this migration.
