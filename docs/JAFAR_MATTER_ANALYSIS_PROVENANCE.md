# Matter → Analysis provenance

Current classification: **M3** for schema, **W1** for the locally accepted V2 producer. The canonical `public.ai_analyses` table stores `id`, `matter_id`, `document_id`, result JSON, source chunks and review fields. `LegalAnalysis` is transient; the durable row is `ai_analyses`.

Target chain: Matter → Document → `ai_analyses` → Legal Position item → source reference. Both matter and document IDs must be validated against the same document relationship before exposure. Multiple analyses per document remain allowed. No migration is created or applied in this package.

The current runtime writer is `SupabaseProcessingResultStore.save` (`src/jafar/processing_persistence.py`), which calls V2 with deterministic processing and analysis identities. Local W1 acceptance proved authoritative IDs, replay/concurrency safety, rollback, re-analysis, cross-Matter rejection, and real write→read through `LegalPositionReadService`. Production apply remains forbidden; legacy analyses without both IDs remain non-addressable for Matter UI.

Security: server-side repository access only; no Swift Supabase credentials, raw text, storage paths or embeddings. Lawyer review remains explicit (`requires_lawyer_review`/`review_status`); AI output is advisory.
