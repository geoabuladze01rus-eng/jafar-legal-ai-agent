# Jafar — AI Legal Agent

Jafar is a private, Matter-centric AI system for legal work. The canonical JAFAR 2.0 consolidation line combines document analysis, matter context, evidence/provenance controls, retrieval, long-term memory, email/workspace intake, Apple voice workflows and controlled external actions behind one security boundary.

Current package version: **0.13.0**.

## Canonical architecture

```text
Apple / API / connected intake
            ↓
      authenticated API
            ↓
      Matter / Intake layer
            ↓
      DocumentWorkflow
            ↓
 facts · chronology · deadlines · evidence gaps
            ↓
 Matter RAG / legal research / memory
            ↓
       ModelRouter
       ↙        ↘
 local Ollama   permitted cloud providers
            ↓
      structured legal analysis
            ↓
       human review
            ↓
     controlled execution
```

### Matter is the unit of legal work

Jafar keeps document analysis and retrieval bound to a Matter rather than treating every prompt as an isolated chat. Explicit `matter_id` binding is preserved through document analysis; automatic matter matching is available when the caller does not provide one.

### Document processing

- PDF, DOCX and text intake through the canonical document pipeline.
- Structured `LegalAnalysis` output.
- Matter-aware analysis and deadline extraction.
- Provenance/evidence-gap boundaries for material conclusions.
- Read-only analysis by default; persistence or consequential action remains behind explicit control boundaries.

### Matter RAG and legal research

The canonical stack contains Matter-scoped retrieval and legal-research services. Retrieved context remains tied to stored source material so answers can carry citations/provenance instead of silently turning model output into evidence.

### Local-first confidential AI

Confidential legal text is routed local-first through Ollama when the local provider is available.

Default local configuration:

```dotenv
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b
CONFIDENTIAL_CLOUD_FALLBACK=false
```

The Ollama adapter accepts loopback hosts only for confidential processing, requests structured JSON-schema output and validates the result with the same Pydantic legal model used by the rest of Jafar.

If local Ollama is unavailable, Jafar does **not** silently send confidential text to a cloud model. The default route fails closed to the deterministic local analyzer. Confidential cloud fallback can be enabled only through explicit runtime configuration.

See `docs/ollama-local.md`.

### Google Workspace

The canonical Google integration uses OAuth 2.0 with:

- signed, time-bounded and one-time OAuth state;
- offline authorization / refresh-token lifecycle;
- protected persistent credential storage in the configured production token store;
- read-only Gmail and Calendar access in the current private-beta boundary;
- explicit API/network/auth error handling without exposing credential material.

Google write actions are not part of the default read-only path.

### Apple client and voice

The repository contains the Apple client for iOS/macOS, authenticated API access, App Intents/Shortcuts integration, voice-command routing and approval-aware command execution. Both iOS Simulator and macOS builds are release gates for the consolidation branch.

### Memory and controlled automation

The canonical stack includes long-term legal memory, Matter resolution, approval/reconciliation primitives, audit boundaries and controlled execution. Consequential legal or external actions must not be executed silently.

## Security invariants

1. No credentials, tokens, private documents or client secrets belong in Git.
2. Incoming documents, email and external text are untrusted input.
3. Document facts, allegations, court conclusions and defense positions must not be collapsed into one undifferentiated fact stream.
4. Material legal conclusions should retain source provenance and surface evidence gaps.
5. Confidential cloud processing is opt-in, not an automatic fallback.
6. Consequential external actions require an explicit approval/execution boundary.
7. Production and `main` are not updated until the consolidation release gates are green and reviewed.

## Local development

Python 3.11+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn jafar.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

For local Ollama:

```bash
ollama pull qwen3:4b
ollama list
```

Copy `.env.example` to `.env` and add only the credentials/features that are intentionally enabled for the current environment.

## Release gates

Every PR targeting `release/jafar-2.0-consolidation` must execute the normal Python and Apple gates.

Python:

```bash
ruff check .
python -m compileall -q src
pytest -q
```

Apple:

- generate the Xcode project with XcodeGen;
- build the iOS Simulator target;
- build the macOS target.

Subsystem gates may add focused checks, but they do not replace the full-project gate.

## JAFAR 2.0 consolidation status

The current development strategy is deliberately conservative:

- one canonical consolidation branch;
- small reviewable integration PRs;
- no large new features from stale `main`;
- Ollama has been ported into the canonical router/privacy/DocumentWorkflow stack;
- Google OAuth/Workspace is being consolidated on the same line;
- remaining release gates include Matter RAG E2E, the real-document legal acceptance contract and final security review.

The final consolidation PR must **not** be merged to `main` merely because individual subsystem tests pass. The release candidate must be green as one system on one reviewed commit.
