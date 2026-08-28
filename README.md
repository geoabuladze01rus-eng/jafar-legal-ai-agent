# ЮСТИЦИЯ AI

**Интеллектуальная система адвоката**

`JAFAR` remains the internal technical codename for the legal-intelligence engine and repository architecture. The external product identity approved for release is **ЮСТИЦИЯ AI**.

## Core product boundary

ЮСТИЦИЯ AI is a lawyer-controlled legal intelligence system for document analysis, evidence/provenance review, deadlines, legal research, multi-model verification, drafting assistance, voice workflows and controlled external actions.

The product is designed around four layers:

1. Evidence
2. Legal Intelligence
3. Lawyer Decision
4. Controlled Execution

No model output becomes a fact solely because a model produced it. Mutating or external legal actions require explicit human approval and auditability.

## Cost & scale

Commercial release must keep JAFAR Cost & Scale Control enabled: token metering, configurable provider pricing, spend budgets, atomic spend reservation, provider kill switches, bounded queues, rate limiting, retry/fallback controls and safe reusable caching.
