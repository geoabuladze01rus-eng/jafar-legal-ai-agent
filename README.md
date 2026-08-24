# Jafar — AI Legal Agent

Private AI assistant for legal practice: document analysis, email triage,
drafting, deadlines, voice workflows and controlled automation.

## Current foundation

- FastAPI service with `/health` and `/v1/analyze` endpoints.
- Typed legal domain primitives for criminal, arbitration, civil and
  administrative work.
- Architecture and security boundaries documented in `docs/ARCHITECTURE.md`.
- Environment template without credentials.
- API smoke tests.

## Local start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn jafar.main:app --reload
```

Health check: `GET http://127.0.0.1:8000/health`

## Roadmap

1. Model provider and structured legal-analysis pipeline.
2. Document/OCR ingestion and persistent matter storage.
3. Gmail/Google Drive/calendar connectors.
4. Apple voice/client layer for Mac, iPhone and iPad.
5. Telegram workflow with approval gates.
6. Production security, audit log, observability and deployment.

## Security rule

No credentials, tokens, private documents or client secrets belong in Git.
Consequential external actions require explicit approval.

## Operations

- [Production document pipeline](docs/DOCUMENT_PIPELINE.md)
- [Production-readiness and synthetic E2E runbook](docs/PRODUCTION_RUNBOOK.md)
