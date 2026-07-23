# Setup — Phase 0 & 1

Estimated time: ~1 hour. Everything here is free.

## 1. Supabase (database)

1. Create an account at supabase.com and a new project (pick the Singapore
   region for lowest latency from Thailand). Save the database password.
2. In the project, open **SQL Editor → New query**, paste the contents of
   `db/schema.sql`, and run it. This creates all tables and seed categories.
3. Open **Settings → API** and copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role** key → `SUPABASE_SERVICE_KEY` (backend only — keep secret)
   - **anon/public** key → `SUPABASE_ANON_KEY` (dashboard read side)

### Let the phone insert rows (Row Level Security)

The phone will POST into `raw_events` using the anon key. Two options:

- **Simplest (fine for a private personal project):** in **Authentication →
  Policies**, keep RLS off for `raw_events`, OR add an insert-only policy:

  ```sql
  alter table raw_events enable row level security;
  create policy "anon can insert raw events"
    on raw_events for insert
    to anon
    with check (true);
  ```

  This lets anyone with the anon key *insert* raw events but not read your
  transactions. The processor uses the service key and bypasses RLS.

## 2. GitHub (processor)

1. Create a new GitHub repo and push this project to it.
2. In the repo: **Settings → Secrets and variables → Actions → New repository
   secret**, add:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
3. Go to the **Actions** tab, enable workflows, and click **Run workflow** on
   *process-transactions* to test. After this it runs every 30 minutes.

> Note: GitHub pauses scheduled workflows on repos with no commits for 60 days.
> An occasional commit (or the dashboard traffic) keeps things alive.

## 3. Phone (capture)

Follow `docs/macrodroid.md` to forward KBANK / UOB LINE notifications into
`raw_events`. Test by making a small transfer and confirming a row appears in
Supabase (**Table editor → raw_events**), then that a `transactions` row appears
after the next processor run (or a manual run).

## 4. Dashboard

1. First, lock down table access: run `db/migrations/002_lock_rls.sql` in the
   Supabase SQL editor. After this the phone's anon key can only insert
   raw_events; it cannot read your transactions.
2. Push the repo to GitHub (done above).
3. Go to share.streamlit.io, connect the repo, set the main file to
   `dashboard/app.py`.
4. In the app's **Settings → Secrets**, add (note: the **service** key — it stays
   server-side on Community Cloud and is never sent to the browser):
   ```toml
   SUPABASE_URL = "https://xxxx.supabase.co"
   SUPABASE_SERVICE_KEY = "your-service_role-key"
   APP_PASSWORD = "choose-a-password"
   ```
5. Open the app URL, enter the password, and you should see your transactions.

## 5. Tune the parsers

Make a couple of real transfers, then look at the `raw_events` payloads in
Supabase. Copy 2–3 (redact names/numbers) and update the sample strings in
`tests/test_parsers.py` and the regex in `src/parsers/kbank.py` / `uob.py` so
they match your banks' exact wording. Run `pytest -q` until green.

## Local development (optional)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # fill in the values
python -m src.process   # run the processor once
streamlit run dashboard/app.py
```
