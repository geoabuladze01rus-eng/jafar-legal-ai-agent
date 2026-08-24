-- Internal worker claim RPC must not be callable through the public PostgREST roles.
revoke execute on function public.claim_document_pipeline_job(text, integer) from anon, authenticated;
grant execute on function public.claim_document_pipeline_job(text, integer) to service_role;
