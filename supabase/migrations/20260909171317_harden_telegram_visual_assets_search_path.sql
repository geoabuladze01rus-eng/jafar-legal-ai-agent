create or replace function public.touch_telegram_visual_assets_updated_at()
returns trigger
language plpgsql
set search_path = public, pg_catalog
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

revoke all on function public.touch_telegram_visual_assets_updated_at()
  from public, anon, authenticated;
grant execute on function public.touch_telegram_visual_assets_updated_at()
  to service_role;
