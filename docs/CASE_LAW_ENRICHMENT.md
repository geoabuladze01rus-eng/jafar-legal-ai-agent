# Case-law document enrichment

The enrichment layer operates after source discovery and before legal-authority verification.

## Pipeline

1. Fetch the full court-document page with `CaseLawDocumentFetcher`.
2. Preserve both the raw-response fingerprint and the normalized-text fingerprint.
3. Extract candidate requisites, statute references, legal topics and proposition candidates.
4. Convert extracted references into `AuthorityCandidate` objects.
5. Send candidates to canonical verification and applicability review.
6. Only verified+applicable authorities may proceed to precedent freshness and ingestion.

## Trust boundary

Enrichment is not verification. A sentence that looks like a court holding remains a `PropositionCandidate`, with conservative confidence and mandatory human review. Regex/topic heuristics do not establish the legal meaning of a case.

Discovery-only sources cannot supply a canonical URL to an `AuthorityCandidate`; the official counterpart must be resolved separately. Even canonical source items cannot enter ingestion directly from enrichment.

## Acceptance gates

- Full-document fetch preserves raw and normalized fingerprints.
- Scripts/styles/noscript content must not contaminate visible-text extraction.
- Statute/case/date extraction produces candidates only.
- Proposition candidates remain reviewable and are never labeled verified.
- Discovery-only enrichment cannot manufacture canonical provenance.
- `may_enter_ingestion_directly` remains false for every enriched candidate.
