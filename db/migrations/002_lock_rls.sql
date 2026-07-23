-- Migration 002 — lock down table access.
-- Run once in the Supabase SQL editor.
--
-- After this, the public anon key (used by the phone) can ONLY insert into
-- raw_events. It cannot read your transactions or other tables. The processor
-- and dashboard use the service_role key, which bypasses RLS.

-- Enable RLS on the data tables (no anon policies => anon has no access).
alter table transactions      enable row level security;
alter table accounts          enable row level security;
alter table categories        enable row level security;
alter table subcategories     enable row level security;
alter table counterparty_rules enable row level security;

-- raw_events already has RLS enabled with an anon INSERT policy (from SETUP.md).
-- Make sure it does NOT allow anon to SELECT: only the insert policy should exist.
-- (If you added any anon select policy earlier, drop it.)
