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

## Case theory engine

`CaseTheoryEngine` combines source-backed claims, cross-document contradictions and timeline contradictions into one auditable theory map. Each claim receives one of four statuses:

- `supported` — source-backed and not currently contradicted by the available graph;
- `contradicted` — a supported opposing claim exists on the same topic;
- `unsupported` — the claim has no valid evidence trail and is not promoted into the factual theory;
- `review_required` — the claim's source participates in a temporal contradiction or another unresolved chronology signal.

The engine preserves the source references for every issue and exposes status counts for lawyer triage. Status is a workflow classification, not a judicial finding. `supported` does not mean proven, `contradicted` does not mean false, and the engine never chooses prosecution or defense theory as true by itself.

## Prosecution and defense theory views

`ProsecutionDefenseTheoryView` projects the shared `CaseTheoryReport` into separate prosecution, defense and neutral views without creating separate factual universes. Both sides continue to reference the same evidence graph and the same source IDs.

When prosecution and defense items share a topic, Jafar creates a `TheoryConflictPoint` that preserves both source trails. This allows the interface to show the prosecution proposition beside the defense counter-proposition with the exact documents, pages, chunks and excerpts supporting each side.

A defense counter-position can be marked as challenging a prosecution proposition when it is source-backed, but the view never declares a winner and never treats a side label as proof. Neutral or uncertain issues remain outside both advocacy views until a lawyer classifies them.

## Prosecution attack surface

`ProsecutionAttackSurfaceEngine` ranks prosecution propositions for lawyer review using transparent, additive vulnerability signals. The score is a triage score only; it is not a probability of acquittal, a finding of inadmissibility or a conclusion that the prosecution thesis is false.

Signals include a supported contradiction, unresolved timeline review, missing provenance, reliance on a single concrete source, lack of independent-document confirmation, dependence on one actor and the presence of a source-backed defense counter-proposition. Each ranked item preserves both prosecution and defense source trails and produces suggested review focus such as checking independent corroboration or reconciling chronology.

High scores identify places where a defense lawyer should spend attention first. They do not authorize Jafar to draft or file a procedural attack without lawyer review.

## Defense action planner

`DefenseActionPlanner` converts ranked weak points into explicit preparation tasks for the lawyer. It can suggest source verification, contradiction comparison, timeline reconstruction, witness-question preparation, identification of missing documents, expert-question preparation and a draft-only procedural-motion task.

Every generated action preserves the relevant source references and has `requires_lawyer_approval=true`. The planner never chooses a legal remedy as final, never sends a request, never files a motion, never contacts a witness and never schedules an external action by itself. A motion action means only “prepare a draft for lawyer review”; the lawyer must separately choose the procedural instrument, legal basis, wording and whether it should be filed.

The plan is sorted by the weakness score inherited from the attack-surface layer so that the most vulnerable prosecution propositions are investigated first. This is a workflow priority, not a conclusion that a challenge will succeed.

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
- Case-theory statuses must preserve source references and must never be presented as truth findings.
- Prosecution/defense views must use the same evidence graph, preserve both source trails and never declare an automatic winner.
- Attack-surface ranking must be explainable from explicit vulnerability signals and must not be presented as a legal conclusion or outcome probability.
- Defense actions must remain preparation tasks, preserve source references and require explicit lawyer approval before any external action.
- Unsupported claims, malformed output and invalid source references require human review.
- Sending email, modifying records, publishing, filing or scheduling remains behind Jafar's action-approval layer.
