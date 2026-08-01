-- Migration 009 — PDF statement import: THB reconciliation + balance anchors.
-- Run once in the Supabase SQL editor.

-- 1) thb_amount: the authoritative THB value of a transaction whose `amount` is
--    in a foreign currency. A live UOB alert only knows the foreign amount (e.g.
--    USD 21.40); the monthly statement supplies the real THB (733.73). Reporting
--    uses thb_amount when set, else `amount` (when currency = 'THB').
alter table transactions add column if not exists thb_amount numeric(14, 2);

-- 2) card_statements: one row per card per statement month. The closing balance
--    ANCHORS a credit card's true unpaid balance. Dashboard unpaid =
--    closing_balance + (charges after statement_date) − (payments after it).
create table if not exists card_statements (
    id               bigserial primary key,
    bank             text not null default 'UOB',
    card_masked      text not null,                 -- last 4
    statement_date   date not null,
    closing_balance  numeric(14, 2) not null,       -- TOTAL BALANCE for the card
    previous_balance numeric(14, 2),
    min_payment      numeric(14, 2),
    due_date         date,
    raw_event_id     bigint references raw_events(id) on delete set null,
    created_at       timestamptz not null default now(),
    unique (bank, card_masked, statement_date)
);
create index if not exists idx_card_statements_card
    on card_statements (bank, card_masked, statement_date);
