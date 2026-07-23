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
