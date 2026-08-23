-- CONSOLIDATION: privileged document-search function must not inherit a mutable role search_path.
-- Keep the function body unchanged; only pin name resolution to trusted schemas.

ALTER FUNCTION public.match_document_chunks(vector, integer, jsonb)
  SET search_path = public, pg_catalog;
