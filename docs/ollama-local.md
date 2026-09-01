# Local Ollama provider

Jafar can use Ollama as the first AI provider for confidential text and legal document analysis.
The default model is `qwen3:4b`, selected for lightweight local use.

## 1. Install and start Ollama

Install Ollama on macOS, start the Ollama application/service, then pull the model:

```bash
ollama pull qwen3:4b
ollama list
```

The local API is expected at:

```text
http://127.0.0.1:11434
```

## 2. Configure Jafar

Copy the relevant values from `.env.example` into `.env`:

```dotenv
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_TIMEOUT_SECONDS=120
OLLAMA_HEALTH_TIMEOUT_SECONDS=0.35
OLLAMA_KEEP_ALIVE=5m
OLLAMA_THINK=false
```

For the confidential local route, `OLLAMA_BASE_URL` must resolve to a loopback host: `127.0.0.1`, `localhost`, or `::1`. Jafar fails closed instead of treating a LAN or remote Ollama server as local.

An OpenAI API key is optional for local-only development. When configured, OpenAI is an allowed fallback for confidential legal analysis if the local Ollama model is unavailable.

## 3. Start Jafar

```bash
uvicorn jafar.main:app --reload
```

Check the service:

```bash
curl http://127.0.0.1:8000/health
```

Run a structured legal analysis:

```bash
curl -X POST http://127.0.0.1:8000/v1/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Автомобиль был изъят 22.10.2024.",
    "task": "legal_analysis",
    "matter_type": "criminal"
  }'
```

## Routing rules

- Confidential text: loopback Ollama first.
- If Ollama is disabled, unavailable, remote, or the configured model is not installed: OpenAI may be used when configured and permitted.
- If no permitted AI provider is available: Jafar falls back to the existing heuristic analyzer.
- Non-confidential specialist tasks keep the existing provider routing rules.

## Structured output

For document tasks, Jafar sends `LegalAnalysis.model_json_schema()` to Ollama's `/api/chat` `format` field, disables streaming, uses temperature `0`, then validates the returned JSON with Pydantic before accepting it.
