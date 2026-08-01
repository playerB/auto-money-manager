"""Deduplication helpers.

Two layers:
  1. dedup_key  — a deterministic hash for exact-repeat protection (unique
     constraint in the DB). Guards against the same notification arriving twice.
  2. fuzzy near-duplicate (in db.find_near_duplicate) — same amount within a
     short time window, used to merge a LINE alert + OneDrive slip + statement
     line that describe one real transfer.
"""
from __future__ import annotations

import hashlib

from .parsers import ParsedTxn


def build_dedup_key(txn: ParsedTxn) -> str:
    minute = txn.ts.replace(second=0, microsecond=0).isoformat()
    counterparty = (txn.counterparty_name or "").strip().lower()
    basis = "|".join(
        [
            txn.bank,
            txn.direction,
            f"{txn.amount:.2f}",
            minute,
            counterparty,
            txn.account_masked or "",
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def build_statement_dedup_key(
    bank: str,
    card_masked: str,
    statement_date: str,
    seq: int,
    amount: float,
    direction: str,
) -> str:
    """Stable key for a statement line.

    A statement can list two genuinely-distinct identical charges on the same day
    (e.g. two 12.00 7-Eleven taps), so the transaction-level dedup_key (which
    would collide) is unsafe here. We key on the statement identity + the row's
    position within it, which is deterministic across re-uploads of the same
    statement — so re-importing is idempotent while distinct rows stay distinct.
    """
    basis = "|".join(
        [
            "stmt",
            bank,
            card_masked or "",
            statement_date,
            str(seq),
            f"{amount:.2f}",
            direction,
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]
