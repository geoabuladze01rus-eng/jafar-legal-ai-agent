create or replace function public.get_notion_token_for_sync()
returns text
language sql
stable
security definer
set search_path = public, vault
as $$
  select decrypted_secret
  from vault.decrypted_secrets
  where name = 'notion_token'
  limit 1;
$$;

revoke all on function public.get_notion_token_for_sync() from public, anon, authenticated;
grant execute on function public.get_notion_token_for_sync() to service_role;
