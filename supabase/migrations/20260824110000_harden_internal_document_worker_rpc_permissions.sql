-- Harden internal document worker claim RPCs.
-- These SECURITY DEFINER functions are used only by trusted workers and must not be callable by anon/authenticated clients.
revoke execute on function public.claim_document_pipeline_job(text, integer) from anon, authenticated;
revoke execute on function public.claim_document_ocr_job(text, integer) from anon, authenticated;
grant execute on function public.claim_document_pipeline_job(text, integer) to service_role;
grant execute on function public.claim_document_ocr_job(text, integer) to service_role;
