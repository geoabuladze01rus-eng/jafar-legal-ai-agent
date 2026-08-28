create or replace function public.create_matter_for_owner(
  p_owner_user_id text,
  p_matter_id uuid,
  p_title text,
  p_matter_type text,
  p_client_name text default null,
  p_opposing_party text default null,
  p_court_or_authority text default null,
  p_case_number text default null,
  p_status text default 'active',
  p_created_at timestamptz default now(),
  p_updated_at timestamptz default now(),
  p_deadlines jsonb default '[]'::jsonb
)
returns public.matters
language plpgsql
security invoker
set search_path = public, pg_catalog
as $$
declare
  v_matter public.matters;
  v_deadline jsonb;
  v_confidence double precision;
begin
  if p_owner_user_id is null or btrim(p_owner_user_id) = '' then
    raise exception 'owner_user_id_required';
  end if;
  if p_title is null or btrim(p_title) = '' then
    raise exception 'matter_title_required';
  end if;
  if jsonb_typeof(coalesce(p_deadlines, '[]'::jsonb)) <> 'array' then
    raise exception 'deadlines_must_be_array';
  end if;

  insert into public.matters
    (
      id,
      owner_user_id,
      title,
      matter_type,
      client_name,
      opposing_party,
      court_or_authority,
      case_number,
      status,
      created_at,
      updated_at
    )
  values
    (
      p_matter_id,
      p_owner_user_id,
      p_title,
      p_matter_type,
      p_client_name,
      p_opposing_party,
      p_court_or_authority,
      p_case_number,
      p_status,
      p_created_at,
      p_updated_at
    )
  returning * into v_matter;

  for v_deadline in
    select * from jsonb_array_elements(coalesce(p_deadlines, '[]'::jsonb))
  loop
    if coalesce(v_deadline->>'title', '') = '' then
      raise exception 'deadline_title_required';
    end if;
    v_confidence := coalesce((v_deadline->>'confidence')::double precision, 0.0);
    if v_confidence < 0.0 or v_confidence > 1.0 then
      raise exception 'deadline_confidence_out_of_range';
    end if;

    insert into public.deadlines
      (matter_id, owner_user_id, title, due_date, source_text, confidence)
    values
      (
        p_matter_id,
        p_owner_user_id,
        v_deadline->>'title',
        case
          when nullif(v_deadline->>'due_date', '') is null then null
          else (v_deadline->>'due_date')::timestamptz
        end,
        v_deadline->>'source_text',
        v_confidence
      );
  end loop;

  return v_matter;
end;
$$;

revoke all on function public.create_matter_for_owner(
  text, uuid, text, text, text, text, text, text, text, timestamptz, timestamptz, jsonb
) from public;
revoke all on function public.create_matter_for_owner(
  text, uuid, text, text, text, text, text, text, text, timestamptz, timestamptz, jsonb
) from anon;
revoke all on function public.create_matter_for_owner(
  text, uuid, text, text, text, text, text, text, text, timestamptz, timestamptz, jsonb
) from authenticated;
grant execute on function public.create_matter_for_owner(
  text, uuid, text, text, text, text, text, text, text, timestamptz, timestamptz, jsonb
) to service_role;
