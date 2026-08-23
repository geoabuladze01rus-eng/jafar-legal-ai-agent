-- CONSOLIDATION: pin name resolution for document vector search.
-- The function is SECURITY INVOKER; this is a defense-in-depth hardening measure.

ALTER FUNCTION public.match_document_chunks(vector, integer, uuid)
  SET search_path = public, pg_catalog;
