-- Migration 001 — add bank + account_masked to transactions.
-- Run this once in the Supabase SQL editor on an already-deployed schema.
-- (Fresh installs from schema.sql already include these columns.)

alter table transactions add column if not exists bank text;
alter table transactions add column if not exists account_masked text;

-- Helps the fuzzy same-bank dedup query.
create index if not exists idx_transactions_bank_amount_ts
    on transactions (bank, amount, ts);
