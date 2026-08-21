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
