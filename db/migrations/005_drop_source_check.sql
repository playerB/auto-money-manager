-- Migration 005 — remove the source CHECK constraints entirely.
-- Run once in the Supabase SQL editor. Supersedes migration 004: `source` is
-- now unconstrained, so future channels (pdf, cash, new integrations, ...) need
-- no further migration. Safe to run whether or not 004 was applied.

alter table raw_events   drop constraint if exists raw_events_source_check;
alter table transactions drop constraint if exists transactions_source_check;
