"""Thin Supabase data-access helpers used by the processing job."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client, create_client

from . import config


def get_client() -> Client:
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


def download_slip(sb: Client, bucket: str, path: str) -> bytes:
    """Download a slip image from Supabase Storage (service key bypasses RLS)."""
    return sb.storage.from_(bucket).download(path)


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
