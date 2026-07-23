"""UOB credit-card parser — notifications arrive via LINE (sender 'UOB Thai').

Sample (redacted):
    text: "มีการใช้บัตร UOB-8340 @TMN 7-11 1.00 THB วันที่ 23"

Shape: "มีการใช้บัตร UOB-<last4> @<merchant> <amount> THB วันที่ <dd>".
LINE truncates the date to the day, so we fall back to arrival time.
Card usage is always a debit against the credit card.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from . import base
from .base import ParsedTxn

_CARD_RE = re.compile(r"UOB-?(\d{4})", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"([\d,]+\.\d{2})\s*THB", re.IGNORECASE)
# merchant sits between "@" and the amount
_MERCHANT_RE = re.compile(r"@\s*(.+?)\s+[\d,]+\.\d{2}\s*THB", re.IGNORECASE)
# paying the card off (internal movement, not spending)
_CARD_PAYMENT_RE = re.compile(r"ชำระยอดบัตร|ชำระค่าบัตร|card\s*payment", re.IGNORECASE)


@base.register("UOB")
def parse(title: str, text: str, fallback_ts: datetime) -> Optional[ParsedTxn]:
    norm = base.thai_to_arabic(text)
    is_payment = bool(_CARD_PAYMENT_RE.search(norm))

    txn = ParsedTxn(
        amount=0.0,
        direction="debit",
        method="credit_card",
        bank="UOB",
        ts=base.ensure_tz(fallback_ts),  # date is truncated to day -> use arrival
        is_internal=is_payment,
    )

    am = _AMOUNT_RE.search(norm)
    if am:
        txn.amount = float(am.group(1).replace(",", ""))
    else:
        txn.flag("UOB: no amount parsed")

    card = _CARD_RE.search(norm)
    if card:
        txn.account_masked = card.group(1)

    if is_payment:
        txn.counterparty_name = "UOB card payment"
    else:
        mer = _MERCHANT_RE.search(norm)
        if mer:
            txn.counterparty_name = mer.group(1).strip(" .:-")
        else:
            txn.flag("UOB: no merchant parsed")

    return txn
