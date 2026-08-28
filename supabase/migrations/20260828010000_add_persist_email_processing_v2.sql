alter table public.documents add column if not exists document_processing_key text;
alter table public.ai_analyses add column if not exists analysis_run_id uuid;
create unique index if not exists documents_processing_key_uidx on public.documents(document_processing_key) where document_processing_key is not null;
create unique index if not exists ai_analyses_analysis_run_id_uidx on public.ai_analyses(analysis_run_id) where analysis_run_id is not null;

create or replace function public.persist_email_processing_v2(p_payload jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_doc jsonb; v_document_id uuid; v_analysis_id uuid; v_matter_id uuid; v_out jsonb := '[]'::jsonb;
begin
  if p_payload->>'message_id' is null then raise exception 'message_id is required'; end if;
  for v_doc in select value from jsonb_array_elements(coalesce(p_payload->'documents','[]'::jsonb)) loop
    v_matter_id := nullif(v_doc->>'matter_id','')::uuid;
    if nullif(v_doc->>'document_processing_key','') is null then raise exception 'document_processing_key is required'; end if;
    insert into public.documents(matter_id,filename,content_type,source,storage_path,processing_status,document_processing_key)
      values(v_matter_id, coalesce(v_doc->>'filename','attachment'), v_doc->>'content_type', 'email', v_doc->>'storage_path', coalesce(v_doc->>'processing_status','stored'), v_doc->>'document_processing_key')
      on conflict (document_processing_key) where document_processing_key is not null do update set processing_status=excluded.processing_status
      returning id into v_document_id;
    if v_matter_id is not null and v_doc->'analysis' is not null and v_doc->'analysis' <> 'null'::jsonb then
      insert into public.ai_analyses(matter_id,document_id,analysis_type,result,source_chunks,analysis_run_id,requires_lawyer_review,review_status)
        values(v_matter_id,v_document_id,coalesce(v_doc->'analysis'->>'analysis_type','legal_analysis'),coalesce(v_doc->'analysis'->'result',v_doc->'analysis'),'[]'::jsonb,(v_doc->>'analysis_run_id')::uuid,true,'pending')
        on conflict (analysis_run_id) where analysis_run_id is not null do update set result=excluded.result
        returning id into v_analysis_id;
    end if;
    v_out := v_out || jsonb_build_array(jsonb_build_object('document_id',v_document_id,'analysis_id',v_analysis_id,'matter_id',v_matter_id));
    v_analysis_id := null;
  end loop;
  return jsonb_build_object('status','ok','documents',v_out);
end; $$;
revoke execute on function public.persist_email_processing_v2(jsonb) from public, anon, authenticated;
grant execute on function public.persist_email_processing_v2(jsonb) to service_role;
