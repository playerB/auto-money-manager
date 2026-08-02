"""Thin Supabase data-access helpers used by the processing job."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from . import config

# `supabase` is imported lazily inside get_client so this module (and callers
# like process.py) import cleanly without the package present — e.g. for unit
# tests that exercise routing/parsing but never touch the database.


def get_client():
    from supabase import create_client

    config.require_supabase()
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


def fetch_unprocessed_events(sb: Client, limit: int = 200) -> list[dict[str, Any]]:
    """Return raw_events that still need parsing, oldest first."""
    resp = (
        sb.table("raw_events")
        .select("*")
        .eq("processed", False)
        .order("received_at", desc=False)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def load_accounts(sb: Client) -> list[dict[str, Any]]:
    """All configured accounts (bank / credit_card / cash) for internal-transfer
    detection. Small table, fetched once per run."""
    resp = sb.table("accounts").select("*").execute()
    return resp.data or []


def merge_raw_event_payload(sb: Client, event_id: int, extra: dict[str, Any]) -> None:
    """Merge extra keys into a raw_event's payload (e.g. log the EasySlip response)."""
    resp = sb.table("raw_events").select("payload").eq("id", event_id).limit(1).execute()
    payload = (resp.data or [{}])[0].get("payload") or {}
    payload.update(extra)
    sb.table("raw_events").update({"payload": payload}).eq("id", event_id).execute()


def mark_event_processed(
    sb: Client, event_id: int, error: str | None = None
) -> None:
    sb.table("raw_events").update(
        {
            "processed": True,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }
    ).eq("id", event_id).execute()


def transaction_exists(sb: Client, dedup_key: str) -> bool:
    """Exact-repeat guard via the unique dedup_key."""
    resp = (
        sb.table("transactions").select("id").eq("dedup_key", dedup_key).limit(1).execute()
    )
    return bool(resp.data)


def find_near_duplicate(
    sb: Client,
    amount: float,
    ts: datetime,
    window_minutes: int,
    bank: str,
    incoming_source: str,
) -> dict[str, Any] | None:
    """Fuzzy dedup for the SAME real transfer seen from different channels.

    Matches same amount + same bank within +/- window_minutes, but ONLY against
    rows from a *different* source. This is deliberate:
      - it merges a LINE alert with its OneDrive slip / statement line, but
      - it never merges two LINE alerts, so two genuine same-amount transfers a
        few minutes apart are both kept.
    Same-source exact repeats are handled separately by the unique dedup_key.
    """
    lo = (ts - timedelta(minutes=window_minutes)).isoformat()
    hi = (ts + timedelta(minutes=window_minutes)).isoformat()
    resp = (
        sb.table("transactions")
        .select("*")
        .eq("amount", amount)
        .eq("bank", bank)
        .neq("source", incoming_source)
        .gte("ts", lo)
        .lte("ts", hi)
        .limit(1)
        .execute()
    )
    return (resp.data or [None])[0]


def insert_transaction(sb: Client, row: dict[str, Any]) -> dict[str, Any]:
    resp = sb.table("transactions").insert(row).execute()
    return (resp.data or [{}])[0]


def update_transaction(sb: Client, txn_id: int, fields: dict[str, Any]) -> None:
    sb.table("transactions").update(fields).eq("id", txn_id).execute()


def download_slip(sb: Client, bucket: str, path: str) -> bytes:
    """Download a slip image from Supabase Storage (service key bypasses RLS)."""
    return sb.storage.from_(bucket).download(path)


def download_file(sb: Client, bucket: str, path: str) -> bytes:
    """Download any file (e.g. a statement PDF) from Supabase Storage."""
    return sb.storage.from_(bucket).download(path)


def load_cc_transactions(
    sb: Client,
    bank: str,
    cards: list[str],
    lo: datetime,
    hi: datetime,
) -> list[dict[str, Any]]:
    """Existing credit-card transactions for the given cards in a date range,
    used to reconcile a statement against already-captured live rows. Excludes
    rows already sourced from a statement."""
    if not cards:
        return []
    resp = (
        sb.table("transactions")
        .select("*")
        .eq("method", "credit_card")
        .eq("bank", bank)
        .in_("account_masked", cards)
        .gte("ts", lo.isoformat())
        .lte("ts", hi.isoformat())
        .execute()
    )
    rows = resp.data or []
    return [r for r in rows if not str(r.get("source") or "").startswith("statement-")]


def account_window_match(row_masked: str, account_masked: str, account_digits: str) -> bool:
    """True when a live row belongs to the SAME real account as a statement.

    Different sources mask different WINDOWS of the same account number: a KBANK
    app alert shows ...3341 while the statement header prints the full
    057-8-03341-6 (last-4 ...3416) — both 3341 and 3416 sit inside 0578033416. So
    equality of the masked last-4 is the wrong test; we accept a live row when its
    masked digits are a window of the statement's full account digits (or equal
    the statement's own last-4). A live row that captured no account number is
    also accepted, to be matched on amount+time downstream (a KBANK alert without
    a parsed account should still dedup against its statement line)."""
    full = re.sub(r"\D", "", account_digits or "")
    want = re.sub(r"\D", "", account_masked or "")
    m = re.sub(r"\D", "", str(row_masked or ""))
    if not full and not want:
        return True
    if not m:
        return True
    if want and m == want:
        return True
    if full and (m in full or full in m):
        return True
    return False


def load_bank_transactions(
    sb: Client,
    bank: str,
    account_masked: str,
    lo: datetime,
    hi: datetime,
    account_digits: str = "",
) -> list[dict[str, Any]]:
    """Existing bank transactions for one account in a date range, to reconcile
    a bank statement against already-captured notifications/slips. Excludes rows
    already sourced from a statement.

    Account matching is window-aware (see account_window_match): a statement whose
    header shows ...3416 still reconciles against alerts stored as ...3341, since
    both are windows of the same full account number. This is what stops a PDF
    import from creating duplicate rows for transactions the app already captured
    from KBANK notifications."""
    resp = (
        sb.table("transactions")
        .select("*")
        .eq("method", "bank")
        .eq("bank", bank)
        .gte("ts", lo.isoformat())
        .lte("ts", hi.isoformat())
        .execute()
    )
    rows = [
        r for r in (resp.data or [])
        if not str(r.get("source") or "").startswith("statement-")
    ]
    if not account_masked and not account_digits:
        return rows
    return [
        r for r in rows
        if account_window_match(r.get("account_masked"), account_masked, account_digits)
    ]


def upsert_card_statement(sb: Client, row: dict[str, Any]) -> None:
    """Insert or update a card_statements anchor (unique on bank+card+date)."""
    sb.table("card_statements").upsert(
        row, on_conflict="bank,card_masked,statement_date"
    ).execute()


def mark_matching_credit_internal(
    sb: Client,
    bank: str,
    amount: float,
    ts: datetime,
    window_minutes: int,
) -> int:
    """Flag the recipient side of an internal transfer.

    A slip for an own->own transfer produces a debit on the sender bank; the
    matching credit lands separately (e.g. the SCB incoming alert). This marks
    that credit as internal so it isn't counted as income.
    """
    if not bank:
        return 0
    lo = (ts - timedelta(minutes=window_minutes)).isoformat()
    hi = (ts + timedelta(minutes=window_minutes)).isoformat()
    resp = (
        sb.table("transactions")
        .select("id, is_internal")
        .eq("bank", bank)
        .eq("direction", "credit")
        .eq("amount", amount)
        .gte("ts", lo)
        .lte("ts", hi)
        .execute()
    )
    n = 0
    for row in resp.data or []:
        if not row.get("is_internal"):
            sb.table("transactions").update({"is_internal": True}).eq(
                "id", row["id"]
            ).execute()
            n += 1
    return n
