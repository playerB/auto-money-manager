-- Migration 008 — store full account numbers on `accounts`.
-- Run once in the Supabase SQL editor.
--
-- Why: different banks/slips mask different digit windows of the SAME bank
-- account (e.g. SCB shows ...6442 while a KBANK slip shows ...7644). Storing the
-- full number lets us match any masking by substring. Bank accounts only —
-- credit cards are consistently identified by their last 4, so leave full_number
-- null for cards.

alter table accounts add column if not exists full_number text;
