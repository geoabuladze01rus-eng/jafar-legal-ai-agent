# Matter → Analysis provenance

Current classification: **M3** for schema, **W3** for the current producer. The canonical `public.ai_analyses` table already stores `id`, `matter_id`, `document_id`, result JSON, source chunks and review fields. `LegalAnalysis` is a transient Python output; the durable row is `ai_analyses`.

Target chain: Matter → Document → `ai_analyses` → Legal Position item → source reference. Both matter and document IDs must be validated against the same document relationship before exposure. Multiple analyses per document remain allowed. No migration is created or applied in this package.

The current runtime writer is `SupabaseProcessingResultStore.save` (`src/jafar/processing_persistence.py`), which calls `persist_email_processing` with nested document analysis; it does not directly construct an `ai_analyses` payload with deterministic document identity. Therefore classification is W3. No heuristic matching is permitted. Future pipeline propagation must carry the known `matter_id` and `document_id`; legacy analyses without both IDs remain non-addressable for Matter UI.

Security: server-side repository access only; no Swift Supabase credentials, raw text, storage paths or embeddings. Lawyer review remains explicit (`requires_lawyer_review`/`review_status`); AI output is advisory.
