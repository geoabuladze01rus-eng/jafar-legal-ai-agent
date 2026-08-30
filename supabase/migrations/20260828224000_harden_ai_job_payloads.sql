-- Keep ai_jobs as a compact reference envelope, not a duplicate legal-content store.
-- Application code recursively rejects sensitive content keys; the database independently
-- enforces a hard payload-size ceiling and common top-level content-key exclusions.

alter table public.ai_jobs
    add constraint ai_jobs_payload_size_check
        check (octet_length(payload::text) <= 65536),
    add constraint ai_jobs_payload_top_level_sensitive_keys_check
        check (
            not (payload ?| array[
                'prompt',
                'text',
                'content',
                'document_text',
                'document_content',
                'email_body',
                'message_body',
                'transcript',
                'raw_document',
                'attachment_bytes',
                'base64'
            ])
        );
