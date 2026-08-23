create policy "matters owner can read" on public.matters
for select to authenticated
using (owner_user_id = (select auth.uid())::text);

create policy "matters owner can insert" on public.matters
for insert to authenticated
with check (owner_user_id = (select auth.uid())::text);

create policy "matters owner can update" on public.matters
for update to authenticated
using (owner_user_id = (select auth.uid())::text)
with check (owner_user_id = (select auth.uid())::text);

create policy "deadlines owner can read" on public.deadlines
for select to authenticated
using (exists (select 1 from public.matters m where m.id = deadlines.matter_id and m.owner_user_id = (select auth.uid())::text));

create policy "deadlines owner can insert" on public.deadlines
for insert to authenticated
with check (exists (select 1 from public.matters m where m.id = deadlines.matter_id and m.owner_user_id = (select auth.uid())::text));

create policy "deadlines owner can update" on public.deadlines
for update to authenticated
using (exists (select 1 from public.matters m where m.id = deadlines.matter_id and m.owner_user_id = (select auth.uid())::text))
with check (exists (select 1 from public.matters m where m.id = deadlines.matter_id and m.owner_user_id = (select auth.uid())::text));

create policy "matter events owner can read" on public.matter_events
for select to authenticated
using (owner_user_id = (select auth.uid())::text);

create policy "matter events owner can insert" on public.matter_events
for insert to authenticated
with check (owner_user_id = (select auth.uid())::text);

create policy "matter events owner can update" on public.matter_events
for update to authenticated
using (owner_user_id = (select auth.uid())::text)
with check (owner_user_id = (select auth.uid())::text);
