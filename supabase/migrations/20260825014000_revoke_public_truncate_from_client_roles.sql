-- Review candidate only. Do not apply to production until staging/local verification is green.
--
-- RLS does not protect TRUNCATE. Client-facing roles should never need to truncate
-- legal-practice tables, so remove that capability explicitly for existing and future
-- tables in public. service_role is intentionally untouched.

revoke truncate on all tables in schema public from anon, authenticated;

alter default privileges in schema public
revoke truncate on tables from anon, authenticated;
