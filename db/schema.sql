-- Auto Money Manager — Supabase / Postgres schema
-- Run this in the Supabase SQL editor (Dashboard → SQL → New query).
-- Safe to re-run: uses IF NOT EXISTS / ON CONFLICT where possible.

-- ---------------------------------------------------------------------------
-- accounts: your bank accounts, credit cards, and a cash "account".
-- is_own = true means the account belongs to you (used to detect internal
-- transfers between your own accounts / credit-card payments).
-- ---------------------------------------------------------------------------
create table if not exists accounts (
    id            bigserial primary key,
    type          text not null check (type in ('bank', 'credit_card', 'cash')),
    bank_name     text,                       -- e.g. 'KBANK', 'UOB'
    masked_number text,                       -- e.g. 'x1234' (last 4 digits)
    display_name  text,                       -- friendly label
    is_own        boolean not null default true,
    created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- categories / subcategories: user-editable spending taxonomy.
-- ---------------------------------------------------------------------------
create table if not exists categories (
    id         bigserial primary key,
    name       text not null unique,
    is_income  boolean not null default false, -- salary, refunds, etc.
    created_at timestamptz not null default now()
);

create table if not exists subcategories (
    id          bigserial primary key,
    category_id bigint not null references categories(id) on delete cascade,
    name        text not null,
    created_at  timestamptz not null default now(),
    unique (category_id, name)
);

-- ---------------------------------------------------------------------------
-- counterparty_rules: "memorize frequent recipient" logic.
-- When a transaction's counterparty matches a rule, it is auto-categorized.
-- match_type: 'exact' | 'contains' | 'regex'. Lower priority number wins.
-- ---------------------------------------------------------------------------
create table if not exists counterparty_rules (
    id             bigserial primary key,
    match_type     text not null default 'contains'
                       check (match_type in ('exact', 'contains', 'regex')),
    pattern        text not null,
    category_id    bigint not null references categories(id) on delete cascade,
    subcategory_id bigint references subcategories(id) on delete set null,
    priority       int not null default 100,
    created_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- raw_events: every raw ingested payload, kept for audit + reprocessing.
-- The phone (MacroDroid, later the native app) inserts LINE notifications here.
-- The OneDrive poller and PDF importer also land raw payloads here.
-- ---------------------------------------------------------------------------
create table if not exists raw_events (
    id           bigserial primary key,
    source       text not null check (source in ('line', 'onedrive', 'pdf', 'manual')),
    payload      jsonb not null,             -- {title, text, timestamp, ...}
    received_at  timestamptz not null default now(),
    processed    boolean not null default false,
    processed_at timestamptz,
    error        text                        -- set if parsing failed / needs review
);
create index if not exists idx_raw_events_unprocessed on raw_events (processed) where processed = false;

-- ---------------------------------------------------------------------------
-- transactions: the normalized, de-duplicated ledger.
-- dedup_key is a hard unique guard against exact repeats; the processor also
-- does a fuzzy near-duplicate check (same amount within a time window) to merge
-- a LINE alert + OneDrive slip + statement line for the same transfer.
-- ---------------------------------------------------------------------------
create table if not exists transactions (
    id              bigserial primary key,
    ts              timestamptz not null,
    amount          numeric(14, 2) not null,
    direction       text not null check (direction in ('debit', 'credit')),
    method          text not null check (method in ('bank', 'credit_card', 'cash')),
    account_id      bigint references accounts(id) on delete set null,
    counterparty_name text,
    category_id     bigint references categories(id) on delete set null,
    subcategory_id  bigint references subcategories(id) on delete set null,
    source          text not null check (source in ('line', 'onedrive', 'pdf', 'manual')),
    raw_event_id    bigint references raw_events(id) on delete set null,
    dedup_key       text unique,
    is_internal     boolean not null default false, -- own-to-own transfer / card payment
    needs_review    boolean not null default false, -- parser unsure; flag in dashboard
    notes           text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index if not exists idx_transactions_ts on transactions (ts);
create index if not exists idx_transactions_amount_ts on transactions (amount, ts);

-- keep updated_at fresh
create or replace function set_updated_at() returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_transactions_updated_at on transactions;
create trigger trg_transactions_updated_at
    before update on transactions
    for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- Seed a starter category set (safe to re-run).
-- ---------------------------------------------------------------------------
insert into categories (name, is_income) values
    ('Food',          false),
    ('Transport',     false),
    ('Utilities',     false),
    ('Rent',          false),
    ('Shopping',      false),
    ('Entertainment', false),
    ('Health',        false),
    ('Fees',          false),
    ('Internal',      false),   -- own-account transfers / card payments
    ('Other',         false),
    ('Salary',        true),
    ('Income',        true)
on conflict (name) do nothing;
