-- Migration 004 — allow source='slip'.
-- Run once in the Supabase SQL editor.
--
-- The original CHECK constraints only permitted line/onedrive/pdf/manual, so
-- inserting a slip event (or transaction) was silently rejected. Add 'slip'.

alter table raw_events   drop constraint if exists raw_events_source_check;
alter table raw_events   add  constraint raw_events_source_check
    check (source in ('line', 'onedrive', 'pdf', 'manual', 'slip'));

alter table transactions drop constraint if exists transactions_source_check;
alter table transactions add  constraint transactions_source_check
    check (source in ('line', 'onedrive', 'pdf', 'manual', 'slip'));
