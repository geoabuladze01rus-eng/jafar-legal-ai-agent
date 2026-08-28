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

## Evidence graph and provenance

Jafar owns source identifiers. PDF extraction preserves page boundaries while the legacy full-text field remains available for existing workflows. Documents are divided into bounded fragments and each fragment receives a stable evidence identifier derived from the document fingerprint, page and chunk index, for example `document:<sha256>:page:14:chunk:3`.

For non-page-based inputs the identifier still carries a stable chunk index. The AI Council receives both the allowed identifier and the corresponding fragment text. Models are instructed to cite the most specific fragment that directly supports a claim and may use only IDs supplied by Jafar.

A model claim is never treated as a fact. Invented evidence IDs are rejected, recorded as invalid references and force human review. A claim with no valid source reference remains unsupported even if multiple models agree with it.

`CaseEvidenceGraph` links review claims to concrete sources. A source can carry the document name, fingerprint, excerpt, page, chunk index, actor and event ID.

## Cross-document contradiction graph

`CrossDocumentContradictionGraph` compares only supported claims that share the same normalized topic. It never promotes unsupported or unreferenced model output into a contradiction signal.

When two supported claims take opposing positions, the graph preserves both source trails: document, page, chunk, actor, event and excerpt. It marks whether the conflict crosses document boundaries and whether it is between different actors. This supports workflows such as comparing two witness interviews, a witness statement against an investigator decision, or competing expert conclusions.

Every cross-document contradiction requires human review. The graph reports the conflict; it does not decide which source is true.

## Timeline contradiction analysis

`TimelineContradictionAnalyzer` compares only assertions that are backed by valid evidence sources. It can surface conflicting exact dates for the same event, disjoint time windows and assertions that fall outside their own stated temporal bounds.

Every timeline signal preserves the concrete source trail, including document, page, chunk, actor and event ID. The analyzer reports temporal incompatibility only; it never decides which chronology is true or whether the contradiction is legally material.

Unreferenced timeline assertions are ignored and cannot create a contradiction signal.

## Confidentiality

The default policy is fail-closed: confidential requests are restricted to explicitly trusted providers. Adding a provider to confidential processing is a deployment decision and requires review of data residency, retention, contractual terms and professional-secrecy requirements.

## Acceptance gates

- At least two independent successful responses for council mode unless the caller explicitly requests a different minimum.
- No silent downgrade when the required number of council members fails.
- Qwen/Kimi must not receive confidential requests under the default privacy policy.
- Disagreements must remain visible to the calling application.
- Model output must not invent evidence identifiers or promote unsupported claims to facts.
- PDF page boundaries and fragment-level source IDs must survive extraction into Council review.
- Cross-document contradictions must include both concrete source trails.
- Unsupported claims must not produce cross-document contradiction signals.
- Timeline contradictions must include concrete evidence references.
- Unreferenced timeline assertions must not produce contradiction signals.
- Unsupported claims, malformed output and invalid source references require human review.
- Sending email, modifying records, publishing, filing or scheduling remains behind Jafar's action-approval layer.
