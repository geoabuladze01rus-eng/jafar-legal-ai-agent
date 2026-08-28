# Case-law ingestion and active-case impact

## Purpose

This layer turns newly discovered judicial authorities into auditable case-law records and checks whether they should trigger re-review of active matters.

## Pipeline

A new authority must pass the existing gates before it can enter the working case-law repository:

1. canonical authority verification;
2. applicability assessment for the concrete legal topic and relevant date;
3. precedent conflict/freshness analysis;
4. deduplication by citation, court, date and source fingerprint;
5. active-case impact analysis.

An unverified authority is blocked from ingestion. A verified authority can be stored even when applicability or freshness still requires review, but it must remain marked for human review and cannot silently update a legal position.

## Deduplication

`CaseLawRecord.dedupe_key` is derived from normalized citation, court, decision date and source fingerprint. Re-ingesting the same canonical authority produces `duplicate` rather than a second record.

## Active-case impact

`ActiveCaseProfile` declares the legal topics currently relevant to a matter and may also list authority IDs already used in its working legal position.

`CaseImpactAnalyzer` compares each newly ingested authority with active cases. Matching topics create a review signal. A current verified+applicable authority normally creates a high-priority review signal. If the authority is already used in a matter, or precedent freshness is conflicting/superseded/limited/review-required, the impact can become critical.

The impact engine never changes a case theory, pleading, motion or court speech automatically. It only identifies matters that should be re-reviewed by the lawyer.

## Acceptance gates

- Unverified authorities must not enter the case-law repository.
- Duplicate canonical authorities must not create duplicate records.
- Active cases are matched by explicit legal topics, not free-form model similarity alone.
- An authority already used in an active matter must trigger a critical re-check when its status is reprocessed.
- Freshness conflicts and non-applicable authorities require lawyer review.
- Case-impact signals are advisory workflow signals only and must not rewrite legal strategy without lawyer approval.
