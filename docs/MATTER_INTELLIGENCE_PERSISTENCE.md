# Matter Intelligence persistence

All derived records cross `MatterIntelligenceWriter`; engines persist only after successful
structured results exist. The writer strips prompt/provider-secret keys, logs opaque run/matter
identifiers, and returns `analysis_completed_persistence_pending` on storage failure so callers
can reconcile the existing result without replaying a provider call.

| Pipeline | completion result | kind | default safety |
| --- | --- | --- | --- |
| evidence graph/extraction | candidate claims + provenance | evidence | `candidate/unverified` |
| timeline/cross-document | contradiction snapshots | contradiction | `requires_review` |
| authority verification | candidate identity/provenance | authority | discovery unless verified |
| AI Council | participating responses/disagreements | council | requires review |
| case analysis/theory | candidate draft | position | `DRAFT`, never approved |
| hearing/court outline | shared projection | hearing | lawyer approval remains required |

Idempotency uses a deterministic owner/matter/kind/payload fingerprint. A changed payload is an
append-only record; GET projections only read records and never dispatch analysis.

## Staging checklist

1. Confirm the target Supabase project and environment; take a backup/snapshot.
2. Apply migrations through `20260830100000_add_matter_intelligence_records.sql`.
3. Verify RLS is enabled, public/anon/authenticated grants are revoked, and service-role
   select/insert are present.
4. Verify the owner/matter/kind/created-at index and immutable trigger.
5. Run a synthetic service-role write/read smoke test for each intelligence kind.
6. Confirm anon/authenticated direct reads and writes fail; do not run this against production
   from a local shell. Credentials are intentionally not part of this repository.
