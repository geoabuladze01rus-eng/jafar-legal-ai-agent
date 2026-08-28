# Matter → Analysis provenance

Current classification: **M3** for schema, **W3** for the current producer. The canonical `public.ai_analyses` table already stores `id`, `matter_id`, `document_id`, result JSON, source chunks and review fields. `LegalAnalysis` is a transient Python output; the durable row is `ai_analyses`.

Target chain: Matter → Document → `ai_analyses` → Legal Position item → source reference. Both matter and document IDs must be validated against the same document relationship before exposure. Multiple analyses per document remain allowed. No migration is created or applied in this package.

The current runtime writer is `SupabaseProcessingResultStore.save` (`src/jafar/processing_persistence.py`), which calls `persist_email_processing` with nested document analysis. The canonical RPC creates `documents` rows but does not insert `ai_analyses` rows or return the generated document UUID. Therefore classification is W3 and cannot be fixed safely without a production RPC/schema contract change. No heuristic matching is permitted; legacy analyses without both IDs remain non-addressable for Matter UI.

Security: server-side repository access only; no Swift Supabase credentials, raw text, storage paths or embeddings. Lawyer review remains explicit (`requires_lawyer_review`/`review_status`); AI output is advisory.
