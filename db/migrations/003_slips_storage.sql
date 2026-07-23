-- Migration 003 — Storage bucket for transfer-slip images.
-- Run once in the Supabase SQL editor.
--
-- The phone (MacroDroid) uploads slip images here with the anon key; the
-- processor downloads them with the service key (bypasses RLS) to OCR them.

-- Private bucket for slips.
insert into storage.buckets (id, name, public)
values ('slips', 'slips', false)
on conflict (id) do nothing;

-- Allow the anon key to UPLOAD (insert) objects into the slips bucket only.
-- It cannot read them back (no select policy), keeping images private.
drop policy if exists "anon upload slips" on storage.objects;
create policy "anon upload slips"
  on storage.objects for insert
  to anon
  with check (bucket_id = 'slips');
