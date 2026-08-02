"""PDF statement import: parse, reconcile, and anchor card balances.

Flow (source = "statement-<bank>" raw_events, payload={path, bank?}):
  dashboard uploads the PDF to Supabase Storage `statements` and inserts a
  raw_events row -> this module downloads it, decrypts if needed, extracts text,
  parses per-bank, then:
    - reconciles each statement line against already-captured live transactions
      (same card + amount + date window). A match is ENRICHED (real THB for a
      foreign charge, cleared review flag) rather than duplicated;
    - genuinely-new lines are inserted (source="statement-<bank>") — this is the
      historical backfill;
    - each card's closing balance is stored in card_statements to anchor its
      true unpaid balance.

Statements carry a date but no time, so reconciliation matches at day
granularity within STATEMENT_MATCH_DAYS.
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from . import categorize, config, db, owner as owner_mod
from .dedup import build_statement_dedup_key
from .parsers import base
from .parsers.base import ParsedTxn
from .parsers.statement_kbank import KbankRow, parse_kbank_statement
from .parsers.statement_uob import StatementRow, parse_uob_statement

log = logging.getLogger("amm.statements")

STATEMENT_MATCH_DAYS = int(os.environ.get("STATEMENT_MATCH_DAYS", "5"))


# --- PDF text extraction (with optional decryption) -------------------------

def extract_pdf_text(pdf_bytes: bytes, password: str = "") -> str:
    """Extract all text from a (possibly encrypted) PDF, pages joined."""
    import pdfplumber

    kwargs: dict[str, Any] = {}
    if password:
        kwargs["password"] = password
    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes), **kwargs) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


# --- helpers ----------------------------------------------------------------

def _row_to_txn(row: StatementRow, bank: str) -> ParsedTxn:
    """Convert a parsed statement line into a ParsedTxn (a credit-card row)."""
    y, m, d = row.trans_date.year, row.trans_date.month, row.trans_date.day
    if row.is_payment:
        counterparty = f"{bank} card payment"
    else:
        counterparty = row.description or None

    if row.currency != "THB" and row.foreign_amount is not None:
        amount = row.foreign_amount
        currency = row.currency
    else:
        amount = row.thb_amount
        currency = "THB"

    txn = ParsedTxn(
        amount=amount,
        direction=row.direction,
        method="credit_card",
        bank=bank,
        ts=base.build_local_dt(y, m, d),
        counterparty_name=counterparty,
        account_masked=row.card_masked,
        currency=currency,
        thb_amount=row.thb_amount,
    )
    if row.installment:
        txn.note(f"installment {row.installment}")
    if currency != "THB":
        txn.note(f"{currency} {amount:.2f} → THB {row.thb_amount:.2f} (statement)")
    if row.is_payment:
        txn.note("card bill payment (statement)")
    txn.note("from statement")
    return txn


def _live_thb(row: dict[str, Any]) -> Optional[float]:
    """The THB value of an existing transaction, if known."""
    if row.get("thb_amount") is not None:
        return float(row["thb_amount"])
    if str(row.get("currency") or "THB") == "THB":
        return float(row["amount"])
    return None


def _find_live_match(
    live: list[dict[str, Any]],
    consumed: set[int],
    row: StatementRow,
) -> Optional[dict[str, Any]]:
    """Best already-captured transaction for this statement line, or None.

    Matches on card + direction + amount within a day window. Amount matches
    either the THB value or (for a foreign charge) the original foreign amount an
    alert would have stored. Returns the nearest-by-date unconsumed candidate.
    """
    best: Optional[dict[str, Any]] = None
    best_dist: Optional[int] = None
    for cand in live:
        cid = cand.get("id")
        if cid in consumed:
            continue
        if str(cand.get("account_masked") or "") != row.card_masked:
            continue
        if str(cand.get("direction") or "") != row.direction:
            continue

        amount_ok = False
        cthb = _live_thb(cand)
        if cthb is not None and abs(cthb - row.thb_amount) < 0.005:
            amount_ok = True
        if (
            not amount_ok
            and row.foreign_amount is not None
            and abs(float(cand["amount"]) - row.foreign_amount) < 0.005
        ):
            amount_ok = True
        if not amount_ok:
            continue

        cts = cand.get("ts")
        try:
            cdate = datetime.fromisoformat(str(cts).replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            continue
        dist = abs((cdate - row.trans_date).days)
        if dist > STATEMENT_MATCH_DAYS:
            continue
        if best_dist is None or dist < best_dist:
            best, best_dist = cand, dist
    return best


def _enrich_fields(existing: dict[str, Any], row: StatementRow) -> dict[str, Any]:
    """What a statement line adds to a matching live transaction."""
    fields: dict[str, Any] = {}
    if existing.get("thb_amount") is None:
        fields["thb_amount"] = row.thb_amount
    if row.currency != "THB":
        # Live alert may have stored the foreign amount as THB (older bug) — set
        # the currency straight and keep the foreign amount in `amount`.
        if str(existing.get("currency") or "THB") == "THB" and row.foreign_amount is not None:
            fields["currency"] = row.currency
            fields["amount"] = row.foreign_amount
    if existing.get("needs_review"):
        fields["needs_review"] = False
    if not existing.get("counterparty_name") and row.description:
        fields["counterparty_name"] = row.description
    return fields


# --- per-bank orchestration -------------------------------------------------

def process_uob_statement_text(
    sb,
    event_id: int,
    text: str,
    rules,
) -> tuple[dict[str, int], Optional[str]]:
    stmt = parse_uob_statement(text)
    stats = {"inserted": 0, "enriched": 0, "duplicates": 0, "anchored": 0, "rows": 0}

    rows = stmt.all_rows()
    stats["rows"] = len(rows)
    if not rows:
        return stats, "UOB statement: no transaction rows found"

    cards = sorted({c.card_masked for c in stmt.cards})
    dates = [r.trans_date for r in rows]
    lo = datetime.combine(min(dates), datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=STATEMENT_MATCH_DAYS + 1
    )
    hi = datetime.combine(max(dates), datetime.min.time(), tzinfo=timezone.utc) + timedelta(
        days=STATEMENT_MATCH_DAYS + 2
    )
    live = db.load_cc_transactions(sb, "UOB", cards, lo, hi)
    consumed: set[int] = set()

    stmt_date_str = str(stmt.statement_date)

    for card in stmt.cards:
        for seq, row in enumerate(card.rows):
            match = _find_live_match(live, consumed, row)
            if match is not None:
                fields = _enrich_fields(match, row)
                if fields:
                    db.update_transaction(sb, match["id"], fields)
                consumed.add(match["id"])
                stats["enriched"] += 1
                continue

            txn = _row_to_txn(row, "UOB")
            key = build_statement_dedup_key(
                "UOB", row.card_masked, stmt_date_str, seq,
                row.thb_amount, row.direction,
            )
            if db.transaction_exists(sb, key):
                stats["duplicates"] += 1
                continue

            cat_id, subcat_id = categorize.match_category(txn.counterparty_name, rules)
            db.insert_transaction(sb, {
                "ts": txn.ts.isoformat(),
                "amount": round(txn.amount, 2),
                "currency": txn.currency,
                "thb_amount": round(txn.thb_amount, 2) if txn.thb_amount is not None else None,
                "direction": txn.direction,
                "method": txn.method,
                "bank": txn.bank,
                "account_masked": txn.account_masked,
                "counterparty_name": txn.counterparty_name,
                "category_id": cat_id,
                "subcategory_id": subcat_id,
                "source": "statement-uob",
                "raw_event_id": event_id,
                "dedup_key": key,
                "is_internal": row.is_payment,  # bill payment is an own-account move
                "needs_review": txn.needs_review,
                "notes": "; ".join(txn.review_reasons) or None,
            })
            stats["inserted"] += 1

        # Anchor this card's closing balance.
        if card.closing_balance is not None and stmt.statement_date is not None:
            db.upsert_card_statement(sb, {
                "bank": "UOB",
                "card_masked": card.card_masked,
                "statement_date": stmt_date_str,
                "closing_balance": card.closing_balance,
                "previous_balance": card.previous_balance,
                "min_payment": card.min_payment,
                "due_date": str(stmt.due_date) if stmt.due_date else None,
                "raw_event_id": event_id,
            })
            stats["anchored"] += 1

    return stats, None


# --- KBANK bank statement ---------------------------------------------------

def _find_live_bank_match(
    live: list[dict[str, Any]],
    consumed: set[int],
    direction: str,
    amount: float,
    when: datetime,
) -> Optional[dict[str, Any]]:
    """Nearest already-captured bank transaction (same direction + amount within
    the day window) for a statement row, else None."""
    best: Optional[dict[str, Any]] = None
    best_dist: Optional[float] = None
    for cand in live:
        cid = cand.get("id")
        if cid in consumed:
            continue
        if str(cand.get("direction") or "") != direction:
            continue
        if abs(float(cand["amount"]) - amount) >= 0.005:
            continue
        cts = cand.get("ts")
        try:
            cdt = datetime.fromisoformat(str(cts).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        dist = abs((cdt - when).total_seconds())
        if dist > STATEMENT_MATCH_DAYS * 86400:
            continue
        if best_dist is None or dist < best_dist:
            best, best_dist = cand, dist
    return best


def _kbank_row_to_txn(
    row: KbankRow, st, matcher, accounts,
) -> ParsedTxn:
    """Convert a KBANK statement row to a ParsedTxn, incl. internal detection.

    The statement account is, by definition, the owner's. So a row is an internal
    transfer when the OTHER party is also the owner — matched by account number
    (against stored own accounts) or by owner name.
    """
    y, m, d = row.date.year, row.date.month, row.date.day
    if row.time:
        hh, mm = (int(x) for x in row.time.split(":"))
        ts = base.build_local_dt(y, m, d, hh, mm)
    else:
        ts = base.build_local_dt(y, m, d)

    txn = ParsedTxn(
        amount=row.amount,
        direction=row.direction,
        method="bank",
        bank="KBANK",
        ts=ts,
        counterparty_name=row.counterparty_name,
        account_masked=st.account_masked,
        counterparty_bank=row.counterparty_bank,
        counterparty_account=row.counterparty_acct,
        currency="THB",
        thb_amount=row.amount,
    )

    # Internal only makes sense for transfers to/from another party.
    if row.ttype.startswith("Transfer") or row.ttype == "Automatic Deposit":
        acct_own = owner_mod.own_account_match(
            row.counterparty_bank, row.counterparty_acct, accounts
        )
        name_ok, name_strong = matcher.match(row.counterparty_name)
        if acct_own or name_ok:
            txn.is_internal = True
            if acct_own or name_strong:
                txn.note("internal transfer (own account)")
            else:
                txn.flag("internal transfer suspected (name only) — verify")
    if not row.balance_ok:
        txn.flag("statement: amount != balance delta — verify")
    if row.ref:
        txn.note(f"ref {row.ref}")
    txn.note("from statement")
    return txn


def process_kbank_statement_text(
    sb, event_id: int, text: str, rules, accounts,
) -> tuple[dict[str, int], Optional[str]]:
    st = parse_kbank_statement(text)
    stats = {"inserted": 0, "enriched": 0, "duplicates": 0, "anchored": 0,
             "rows": len(st.rows)}
    if not st.rows:
        return stats, "KBANK statement: no transaction rows found"

    matcher = owner_mod.OwnerMatcher(config.OWNER_NAMES)
    accounts = accounts or []

    dates = [r.date for r in st.rows]
    lo = datetime.combine(min(dates), datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=STATEMENT_MATCH_DAYS + 1
    )
    hi = datetime.combine(max(dates), datetime.min.time(), tzinfo=timezone.utc) + timedelta(
        days=STATEMENT_MATCH_DAYS + 2
    )
    live = db.load_bank_transactions(
        sb, "KBANK", st.account_masked or "", lo, hi,
        account_digits=st.account_digits or "",
    )
    consumed: set[int] = set()
    stmt_key = str(st.period_end or st.period_start or "")

    for seq, row in enumerate(st.rows):
        txn = _kbank_row_to_txn(row, st, matcher, accounts)

        match = _find_live_bank_match(live, consumed, txn.direction, txn.amount, txn.ts)
        if match is not None:
            fields: dict[str, Any] = {}
            if txn.is_internal and not match.get("is_internal"):
                fields["is_internal"] = True
            if txn.counterparty_name and not match.get("counterparty_name"):
                fields["counterparty_name"] = txn.counterparty_name
            if fields:
                db.update_transaction(sb, match["id"], fields)
            consumed.add(match["id"])
            stats["enriched"] += 1
            continue

        key = build_statement_dedup_key(
            "KBANK", st.account_masked or "", stmt_key, seq, txn.amount, txn.direction
        )
        if db.transaction_exists(sb, key):
            stats["duplicates"] += 1
            continue

        cat_id, subcat_id = categorize.match_category(txn.counterparty_name, rules)
        db.insert_transaction(sb, {
            "ts": txn.ts.isoformat(),
            "amount": round(txn.amount, 2),
            "currency": "THB",
            "thb_amount": round(txn.amount, 2),
            "direction": txn.direction,
            "method": "bank",
            "bank": "KBANK",
            "account_masked": txn.account_masked,
            "counterparty_name": txn.counterparty_name,
            "category_id": cat_id,
            "subcategory_id": subcat_id,
            "source": "statement-kbank",
            "raw_event_id": event_id,
            "dedup_key": key,
            "is_internal": txn.is_internal,
            "needs_review": txn.needs_review,
            "notes": "; ".join(txn.review_reasons) or None,
        })
        stats["inserted"] += 1

    return stats, None


def process_statement_event(
    sb,
    event_id: int,
    payload: dict,
    received_at,
    bank: str,
    rules=None,
    accounts=None,
) -> tuple[dict[str, int], Optional[str]]:
    """Download + parse + reconcile a statement raw_event. `bank` is from the
    source suffix (statement-<bank>)."""
    path = payload.get("path") or payload.get("storage_path")
    if not path:
        return {}, "statement payload has no storage path"
    prefix = config.STATEMENT_BUCKET + "/"
    if path.startswith(prefix):
        path = path[len(prefix):]

    try:
        pdf_bytes = db.download_file(sb, config.STATEMENT_BUCKET, path)
    except Exception as exc:  # noqa: BLE001
        return {}, f"statement download failed: {exc}"

    password = config.statement_password(bank)
    try:
        text = extract_pdf_text(pdf_bytes, password)
    except Exception as exc:  # noqa: BLE001
        hint = "" if password else " (PDF may be password-protected)"
        return {}, f"statement PDF read failed: {exc}{hint}"

    if rules is None:
        rules = categorize.load_rules(sb)

    bank = (bank or "").upper()
    if bank == "UOB":
        return process_uob_statement_text(sb, event_id, text, rules)
    if bank == "KBANK":
        return process_kbank_statement_text(sb, event_id, text, rules, accounts)
    return {}, f"no statement parser for bank={bank}"
