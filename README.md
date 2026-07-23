# Auto Money Manager

Automatically records your spending from KBANK / UOB LINE notifications (and,
in later phases, OneDrive transfer slips + PDF statements), categorizes it, and
shows weekly/monthly reports — all on free tiers.

## How it works (Phase 0–1)

```
Phone (MacroDroid)  --HTTPS POST-->  Supabase (raw_events)
                                          |
                    GitHub Actions (every 30 min) parses -> transactions
                                          |
                          Streamlit dashboard (reads Supabase)
```

- **Ingestion:** the phone POSTs bank LINE notifications straight into the
  Supabase `raw_events` table (no server to run).
- **Processing:** a scheduled GitHub Action parses new events into normalized,
  de-duplicated `transactions`.
- **Dashboard:** a Streamlit app reads and displays them.

Everything sits inside free tiers. A 1–2 hour delay is fine, which is what makes
the "no always-on server" design possible.

## Repo layout

```
db/schema.sql                 Postgres schema (run in Supabase SQL editor)
src/process.py                main job entrypoint (python -m src.process)
src/parsers/kbank.py          KBANK LINE parser  (tune with real samples)
src/parsers/uob.py            UOB card LINE parser (tune with real samples)
src/dedup.py                  dedup key logic
src/categorize.py             counterparty-rule categorization
dashboard/app.py              Streamlit dashboard (password-gated)
.github/workflows/process.yml scheduled processor
docs/SETUP.md                 step-by-step setup
docs/macrodroid.md            phone notification-forwarding setup
tests/                        parser tests
```

## Quick start

See **docs/SETUP.md** for the full walkthrough. In short:

1. Create a free Supabase project; run `db/schema.sql` in its SQL editor.
2. Push this repo to GitHub; add `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` secrets.
3. Set up MacroDroid on your phone (see `docs/macrodroid.md`) to POST bank
   notifications into `raw_events`.
4. Deploy `dashboard/app.py` to Streamlit Community Cloud (set `APP_PASSWORD`,
   `SUPABASE_URL`, `SUPABASE_ANON_KEY`).

## Run tests

```bash
pip install -r requirements.txt
pytest -q
```

## Note on the parsers

`src/parsers/kbank.py` and `uob.py` use best-effort regex for Thai bank alerts.
Paste 2–3 real (redacted) notifications and update the sample strings in
`tests/test_parsers.py` to lock in your exact formats.
