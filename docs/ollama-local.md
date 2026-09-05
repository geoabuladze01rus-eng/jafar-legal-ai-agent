# Jafar + Ollama: local-first legal analysis

Jafar can use a local Ollama daemon for confidential document analysis before any cloud model is considered.

## Security boundary

- The production adapter accepts only loopback hosts: `127.0.0.1`, `localhost`, or `::1`.
- Confidential legal requests are routed to Ollama by the central `ModelRouter` / `ProviderPrivacyPolicy` composition.
- Cloud fallback for confidential text is disabled by default.
- Set `CONFIDENTIAL_CLOUD_FALLBACK=true` only when the owner explicitly accepts cloud processing for the request class.
- If Ollama is unavailable and cloud fallback is disabled, Jafar fails closed to the deterministic local analyzer rather than silently sending the document to a cloud provider.
- Source documents still pass through the canonical `DocumentWorkflow`; model selection does not bypass Matter matching or review boundaries.

## Recommended local configuration

For an Apple Silicon Mac with 8 GB unified memory, start with a 4B-class model:

```bash
ollama pull qwen3:4b
ollama list
```

`.env`:

```dotenv
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT_SECONDS=120
OLLAMA_HEALTH_TIMEOUT_SECONDS=0.35
OLLAMA_KEEP_ALIVE=5m
OLLAMA_THINK=false
CONFIDENTIAL_CLOUD_FALLBACK=false
```

## Runtime behavior

For a confidential legal-analysis request:

```text
Document
  -> DocumentWorkflow
  -> ModelRouter
  -> ProviderPrivacyPolicy
  -> Ollama localhost
  -> LegalAnalysis JSON schema validation
  -> result
```

If the local daemon/model is unavailable:

```text
Ollama unavailable
  -> no cloud transmission by default
  -> deterministic local LegalAnalyzer
```

If explicit cloud fallback is enabled and OpenAI is configured:

```text
Ollama unavailable
  -> ProviderPrivacyPolicy permits OpenAI
  -> routed cloud fallback
```

## Structured output contract

The adapter sends `LegalAnalysis.model_json_schema()` to Ollama as the `/api/chat` `format`, also includes the schema in the prompt, uses `stream=false` and `temperature=0`, and validates the returned message with Pydantic before Jafar accepts it.

An invalid or malformed response is rejected and never promoted to a valid legal analysis.

## Operational checks

```bash
curl http://127.0.0.1:11434/api/tags
pytest -q tests/test_ollama_provider.py tests/test_routed_legal_analyzer.py tests/test_multimodel_router.py tests/test_privacy_policy.py
```

## Important legal-data rule

Local inference reduces external data exposure but does not make model output authoritative. Jafar must continue to distinguish document facts, allegations, court conclusions and defense positions; material conclusions require provenance and human review before external use.
