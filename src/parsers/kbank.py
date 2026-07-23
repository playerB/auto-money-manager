"""KBANK (Kasikornbank) LINE notification parser.

TODO: tune the patterns below against 2-3 real (redacted) KBANK LINE alerts.
The detection keywords and field extraction are best-effort defaults.

Example shapes this currently handles (illustrative, redacted):
    title: "KBANK"
    text:  "โอนเงิน 1,500.00 บาท จากบัญชี x1234 ไปยัง นายสมชาย ใจดี"
    text:  "รับโอน 2,000.00 บาท เข้าบัญชี x1234 จาก บจก. เอบีซี"
    text:  "ชำระค่าสินค้า 350.00 บาท ร้าน 7-ELEVEN บัญชี x1234"
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from . import base
from .base import ParsedTxn

# Detect a KBANK message from title or body.
_KBANK_HINT = re.compile(r"KBANK|กสิกร|K\s?PLUS|K\+", re.IGNORECASE)

# Try to pull a counterparty after common connectors.
#   "ไปยัง <name>" / "จาก <name>" / "ร้าน <name>" / "to <name>"
_COUNTERPARTY_RE = re.compile(
    r"(?:ไปยัง|ไปที่|จาก|ร้าน|ให้แก่|ให้กับ|to|ที่)\s*[:：]?\s*(.+?)"
    r"(?:\s+(?:บัญชี|เลขที่|ref|อ้างอิง|เวลา)|[。.\n]|$)",
    re.IGNORECASE,
)


@base.register
def parse(title: str, text: str, ts_hint: datetime) -> Optional[ParsedTxn]:
    blob = f"{title}\n{text}"
    if not _KBANK_HINT.search(blob):
        return None

    amount = base.parse_amount(text)
    if amount is None:
        # Recognized as KBANK but couldn't read an amount — surface for review.
        txn = ParsedTxn(
            amount=0.0,
            direction="debit",
            method="bank",
            bank="KBANK",
            ts=base.ensure_tz(ts_hint),
        )
        txn.flag("KBANK message but no amount parsed")
        return txn

    direction = base.guess_direction(blob) or "debit"
    txn = ParsedTxn(
        amount=amount,
        direction=direction,
        method="bank",
        bank="KBANK",
        ts=base.ensure_tz(ts_hint),
        account_masked=base.parse_last4(text),
    )

    m = _COUNTERPARTY_RE.search(text)
    if m:
        name = m.group(1).strip(" .:-")
        if name:
            txn.counterparty_name = name
    else:
        txn.flag("no counterparty parsed")

    if base.guess_direction(blob) is None:
        txn.flag("direction guessed (defaulted to debit)")

    return txn
