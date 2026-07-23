"""Main processing job.

Run every ~30 min by GitHub Actions (or manually). It:
  1. reads unprocessed raw_events from Supabase,
  2. parses each with the bank parsers,
  3. de-duplicates (exact key + fuzzy same-amount/time-window),
  4. auto-categorizes from counterparty_rules,
  5. inserts new transactions and marks events processed.

This run also keeps the free Supabase project from auto-pausing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from . import categorize, config, db
from .dedup import build_dedup_key
from .parsers import dispatch


def _parse_iso(value: Any) -> Optional[datetime]:
    """Parse a Supabase ISO timestamp (received_at) into an aware datetime."""
    if not value:
        return None
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("amm.process")


def _txn_to_row(
    txn, dedup_key: str, event_id: int, source: str, cat_id, subcat_id
) -> dict[str, Any]:
    return {
        "ts": txn.ts.isoformat(),
        "amount": round(txn.amount, 2),
        "direction": txn.direction,
        "method": txn.method,
        "bank": txn.bank,
        "account_masked": txn.account_masked,
        "counterparty_name": txn.counterparty_name,
        "category_id": cat_id,
        "subcategory_id": subcat_id,
        "source": source,
        "raw_event_id": event_id,
        "dedup_key": dedup_key,
        "is_internal": txn.is_internal,
        "needs_review": txn.needs_review,
        "notes": "; ".join(txn.review_reasons) or None,
    }


def run() -> dict[str, int]:
    sb = db.get_client()
    events = db.fetch_unprocessed_events(sb)
    rules = categorize.load_rules(sb)

    stats = {"events": len(events), "inserted": 0, "duplicates": 0, "unparsed": 0}
    log.info("Processing %d unprocessed events", len(events))

    for event in events:
        event_id = event["id"]
        source = event.get("source")

        # Phase 1 handles LINE events; other sources arrive in later phases.
        if source != "line":
            db.mark_event_processed(sb, event_id, error="source not yet handled")
            continue

        payload = event.get("payload") or {}
        received_at = _parse_iso(event.get("received_at"))
        txn = dispatch(payload, received_at)
        if txn is None:
            stats["unparsed"] += 1
            app = str(payload.get("app", "?"))
            db.mark_event_processed(sb, event_id, error=f"no parser for app={app}")
            log.info("event %s: no parser for app=%s", event_id, app)
            continue

        dedup_key = build_dedup_key(txn)

        if db.transaction_exists(sb, dedup_key):
            stats["duplicates"] += 1
            db.mark_event_processed(sb, event_id, error=None)
            log.info("event %s: exact duplicate, skipped", event_id)
            continue

        near = db.find_near_duplicate(
            sb,
            round(txn.amount, 2),
            txn.ts,
            config.DEDUP_WINDOW_MINUTES,
            bank=txn.bank,
            incoming_source=source,
        )
        if near is not None:
            stats["duplicates"] += 1
            db.mark_event_processed(sb, event_id, error=None)
            log.info(
                "event %s: near-duplicate of txn %s, skipped",
                event_id,
                near.get("id"),
            )
            continue

        cat_id, subcat_id = categorize.match_category(txn.counterparty_name, rules)
        row = _txn_to_row(txn, dedup_key, event_id, source, cat_id, subcat_id)
        db.insert_transaction(sb, row)
        stats["inserted"] += 1
        db.mark_event_processed(sb, event_id, error=None)
        log.info(
            "event %s: inserted %s %.2f (%s)",
            event_id,
            txn.direction,
            txn.amount,
            txn.counterparty_name or "?",
        )

    log.info("Done: %s", stats)
    return stats


if __name__ == "__main__":
    run()
