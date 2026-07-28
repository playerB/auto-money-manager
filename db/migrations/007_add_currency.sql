-- Migration 007 — add a currency column to transactions.
-- Run once in the Supabase SQL editor. Existing rows default to THB.

alter table transactions add column if not exists currency text not null default 'THB';
