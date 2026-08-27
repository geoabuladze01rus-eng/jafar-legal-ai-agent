# Jafar — architecture

## Goal
Jafar is a private legal-work assistant for Apple devices. The first release is designed around a secure API and replaceable integrations rather than hard-coding a single vendor.

## Core layers

1. **Interfaces** — iPhone/iPad/Mac voice and chat clients.
2. **API** — authenticated FastAPI service.
3. **Orchestration** — routes requests to document, email, matter, deadline and drafting workflows.
4. **Legal intelligence** — extraction, classification, chronology, issue spotting, risk review and draft generation.
5. **Connectors** — Gmail/Outlook, Google Drive, GitHub, calendar and Telegram.
6. **Storage** — encrypted metadata, matter index and audit log; source documents remain in approved storage.

## Safety principles

- Never send or publish a legal response without explicit user approval.
- Never modify a repository, email, calendar or external record silently.
- Separate facts extracted from documents from model conclusions.
- Keep an audit trail for every external action.
- Secrets live in environment/secret storage, never in Git.
- Treat incoming documents and email text as untrusted input.

## Initial workflows

### Email triage
Receive -> classify -> detect legal document -> extract parties/dates/claims -> produce a short legal brief -> draft response -> wait for approval.

### Document analysis
Upload/reference -> OCR/text extraction -> metadata -> chronology -> legal issues -> risks -> requested actions -> concise lawyer brief.

### Voice
Speech -> intent -> confirmation for consequential actions -> workflow -> spoken/text result.

## Integration roadmap

- Phase 1: API foundation, legal domain model, tests and local development.
- Phase 2: model provider + document pipeline + persistent storage.
- Phase 3: local Gmail read-only workflow is complete; Drive and calendar workflows remain.
- Phase 4: Apple client/voice shell is in Private Beta; production notifications remain.
- Phase 5: Telegram publishing/replies with approval gates.
- Phase 6: production security, observability and deployment.
