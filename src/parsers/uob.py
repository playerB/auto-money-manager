"""UOB (Thailand) credit-card LINE notification parser.

TODO: tune against 2-3 real (redacted) UOB card alerts.

Example shapes this currently handles (illustrative, redacted):
    title: "UOB"
    text:  "การใช้จ่ายผ่านบัตร UOB xxxx1234 จำนวน 850.00 บาท ที่ GRAB"
    text:  "UOB Card xxxx1234 spent THB 1,299.00 at LAZADA"
    text:  "ชำระยอดบัตรเครดิต 5,000.00 บาท"   -> internal (card payment)
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from . import base
from .base import ParsedTxn

_UOB_HINT = re.compile(r"UOB|ยูโอบี", re.IGNORECASE)

# Merchant after "ที่ <merchant>" / "at <merchant>".
_MERCHANT_RE = re.compile(
    r"(?:ที่|at|ร้าน)\s*[:：]?\s*(.+?)(?:\s+(?:เวลา|ref|อ้างอิง|วันที่)|[。.\n]|$)",
    re.IGNORECASE,
)

# Card-payment (paying off the card) => internal transfer, not spending.
_CARD_PAYMENT_HINT = re.compile(r"ชำระยอดบัตร|ชำระค่าบัตร|card\s+payment", re.IGNORECASE)


@base.register
def parse(title: str, text: str, ts_hint: datetime) -> Optional[ParsedTxn]:
    blob = f"{title}\n{text}"
    if not _UOB_HINT.search(blob):
        return None

    amount = base.parse_amount(text)
    if amount is None:
        txn = ParsedTxn(
            amount=0.0,
            direction="debit",
            method="credit_card",
            bank="UOB",
            ts=base.ensure_tz(ts_hint),
        )
        txn.flag("UOB message but no amount parsed")
        return txn

    is_payment = bool(_CARD_PAYMENT_HINT.search(blob))
    txn = ParsedTxn(
        amount=amount,
        direction="debit",  # a card charge reduces available credit
        method="credit_card",
        bank="UOB",
        ts=base.ensure_tz(ts_hint),
        account_masked=base.parse_last4(text),
        is_internal=is_payment,  # paying the card off is an internal movement
    )

    if is_payment:
        txn.counterparty_name = "UOB card payment"
    else:
        m = _MERCHANT_RE.search(text)
        if m:
            merchant = m.group(1).strip(" .:-")
            if merchant:
                txn.counterparty_name = merchant
        else:
            txn.flag("no merchant parsed")

    return txn
