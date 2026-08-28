# Jafar AI Council

## Purpose

AI Council is Jafar's multi-model review layer. It is designed for legal work where a single model should not silently become the sole source of reasoning.

## Default roles

- OpenAI: primary legal analysis and final orchestration.
- Qwen: independent second opinion and alternative reasoning.
- Kimi: long-context and cross-document review.
- DeepSeek: technical analysis and adversarial reasoning where configured.
- Gemini: vision and Google-context workloads.

## Processing pattern

1. Deterministic extraction establishes the factual baseline.
2. The router chooses the primary provider for the task.
3. Privacy policy determines which providers are permitted to receive the material.
4. AI Council can send the same sanitized/non-confidential request to multiple independent providers.
5. Every successful response is preserved.
6. Provider failures are recorded separately.
7. Structured claims are compared for contradictions and missing evidence.
8. Divergent conclusions are surfaced for human review instead of being averaged away.
9. No external action is authorized by model consensus alone.

## Evidence graph

Jafar owns source identifiers. For a document review it creates a stable evidence identifier from the document fingerprint, for example `document:<sha256>`, and exposes only those identifiers to council models.

A model claim is never treated as a fact. A claim may reference only evidence IDs supplied by Jafar. Invented evidence IDs are rejected, recorded as invalid references and force human review. A claim with no valid source reference remains unsupported even if multiple models agree with it.

`CaseEvidenceGraph` links review claims to concrete sources. A source can carry the document name, fingerprint, excerpt, page, actor, event ID and metadata. This provides the foundation for later page-level and cross-document evidence tracing.

## Confidentiality

The default policy is fail-closed: confidential requests are restricted to explicitly trusted providers. Adding a provider to confidential processing is a deployment decision and requires review of data residency, retention, contractual terms and professional-secrecy requirements.

## Acceptance gates

- At least two independent successful responses for council mode unless the caller explicitly requests a different minimum.
- No silent downgrade when the required number of council members fails.
- Qwen/Kimi must not receive confidential requests under the default privacy policy.
- Disagreements must remain visible to the calling application.
- Model output must not invent evidence identifiers or promote unsupported claims to facts.
- Unsupported claims, malformed output and invalid source references require human review.
- Sending email, modifying records, publishing, filing or scheduling remains behind Jafar's action-approval layer.
