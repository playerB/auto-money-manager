"""Main processing job.

Reads unprocessed raw_events from Supabase, parses each by its `source`,
de-duplicates, auto-categorizes, and writes transactions. Also keeps the free
Supabase project from auto-pausing.

Routing by `source`:
  - "gallery-<album>"  -> a slip image; OCR + slip parser for that album
                          (one album = one bank = one slip style).
  - "line"             -> a LINE notification; routed by payload.app (SCB/UOB).
  - "kplus"/"scb"/"uob" -> a bank-app notification (title/text) parsed directly.
  - anything else       -> recorded as unhandled.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from . import categorize, config, db
from .dedup import build_dedup_key
from .parsers import dispatch, kbank, scb, uob

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("amm.process")

# Bank-app notification sources -> their notification parser.
NOTIF_SOURCE_PARSERS = {
    "kplus": kbank.parse,
    "scb": scb.parse,
    "uob": uob.parse,
}

GALLERY_PREFIX = "gallery-"


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


def _parse_event(sb, source: str, payload: dict, received_at):
    """Return (ParsedTxn|None, error, is_slip) for one event."""
    if source.startswith(GALLERY_PREFIX):
        album = source[len(GALLERY_PREFIX):]
        txn, err = _parse_slip_event(sb, payload, received_at, album)
        return txn, err, True
    if source == "line":
        txn = dispatch(payload, received_at)
        err = None if txn else f"no parser for app={payload.get('app', '?')}"
        return txn, err, False
    if source in NOTIF_SOURCE_PARSERS:
        title = str(payload.get("title", "") or "")
        text = str(payload.get("text", "") or "")
        txn = NOTIF_SOURCE_PARSERS[source](title, text, received_at)
        err = None if txn else f"parser for source={source} did not match"
        return txn, err, False
    return None, f"source not handled: {source}", False


def _reconcile_recipient(sb, txn, event_id: int) -> None:
    """For an internal-transfer slip, flag the recipient-side credit internal."""
    if not (txn.is_internal and txn.counterparty_bank):
        return
    marked = db.mark_matching_credit_internal(
        sb,
        txn.counterparty_bank,
        round(txn.amount, 2),
        txn.ts,
        config.INTERNAL_MATCH_WINDOW_MINUTES,
    )
    if marked:
        log.info(
            "event %s: marked %d recipient credit(s) internal (%s)",
            event_id,
            marked,
            txn.counterparty_bank,
        )


def _enrich_from_slip(sb, existing: dict, txn) -> dict:
    """A slip that near-duplicates an existing notification enriches it with the
    richer slip fields (recipient, internal flag) instead of being dropped."""
    fields: dict[str, Any] = {}
    if txn.is_internal and not existing.get("is_internal"):
        fields["is_internal"] = True
    if txn.counterparty_name and not existing.get("counterparty_name"):
        fields["counterparty_name"] = txn.counterparty_name
    if txn.needs_review and not existing.get("needs_review"):
        fields["needs_review"] = True
    if fields:
        db.update_transaction(sb, existing["id"], fields)
    return fields


def run() -> dict[str, int]:
    sb = db.get_client()
    events = db.fetch_unprocessed_events(sb)
    rules = categorize.load_rules(sb)

    stats = {
        "events": len(events),
        "inserted": 0,
        "duplicates": 0,
        "enriched": 0,
        "unparsed": 0,
    }
    log.info("Processing %d unprocessed events", len(events))

    for event in events:
        event_id = event["id"]
        source = event.get("source") or ""
        payload = event.get("payload") or {}
        received_at = _parse_iso(event.get("received_at"))

        txn, err, is_slip = _parse_event(sb, source, payload, received_at)
        if txn is None:
            stats["unparsed"] += 1
            db.mark_event_processed(sb, event_id, error=err)
            log.info("event %s: %s", event_id, err)
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
            if is_slip:
                # Slip enriches the matching notification (recipient, internal).
                fields = _enrich_from_slip(sb, near, txn)
                _reconcile_recipient(sb, txn, event_id)
                stats["enriched"] += 1
                db.mark_event_processed(sb, event_id, error=None)
                log.info(
                    "event %s: slip enriched txn %s %s",
                    event_id,
                    near.get("id"),
                    fields or "(no new fields)",
                )
            else:
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
            "event %s: inserted %s %s %.2f (%s)",
            event_id,
            txn.bank,
            txn.direction,
            txn.amount,
            txn.counterparty_name or "?",
        )

        if is_slip:
            _reconcile_recipient(sb, txn, event_id)

    log.info("Done: %s", stats)
    return stats


def _parse_slip_event(
    sb, payload: dict, received_at, album: str
) -> tuple[Any, Optional[str]]:
    """Download + OCR + parse a slip raw_event. Returns (ParsedTxn|None, error)."""
    from . import slips

    path = payload.get("path") or payload.get("storage_path")
    if not path:
        return None, "slip payload has no storage path"
    # Accept either "file.jpg" or "slips/file.jpg".
    prefix = config.SLIP_BUCKET + "/"
    if path.startswith(prefix):
        path = path[len(prefix):]
    # Bank hint from the album (one album = one bank), payload override allowed.
    folder_bank = payload.get("bank") or slips.bank_for_album(album)
    try:
        image = db.download_slip(sb, config.SLIP_BUCKET, path)
    except Exception as exc:  # noqa: BLE001
        return None, f"slip download failed: {exc}"
    try:
        text = slips.ocr_image(image)
    except Exception as exc:  # noqa: BLE001
        return None, f"slip OCR failed: {exc}"
    parse = slips.parser_for_album(album)
    txn = parse(text, received_at, config.OWNER_NAMES, folder_bank=folder_bank)
    if txn is None:
        return None, f"slip (album={album}) OCR text not recognized"
    return txn, None


if __name__ == "__main__":
    run()
