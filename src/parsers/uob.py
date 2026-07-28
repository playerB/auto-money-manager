"""UOB credit-card parser — notifications arrive via LINE (sender 'UOB Thai').

Real formats (redacted):
  purchase:     "มีการใช้บัตร UOB-1640 @WWW.GRAB.COM 29.00"
                "มีการใช้บัตร UOB-8340 @(FOR SHOPEE)*(FOR SHOP 1,336.00 THB วันที่ 24/05 วงเงินคงเหลือใช้ได้ 133,071.00 THB"
                "มีการใช้บัตร UOB-9762 @TRENITALIA - LEFRECCE 14.8 EUR วันที่ 24/05 ..."
  cancellation: "มีการยกเลิกทำรายการบัตร UOB-1640 @KAMIKA-CENTRAL RAMA 9 399.00 THB"

Shape: "<ใช้|ยกเลิก>บัตร UOB-<last4> @<merchant> <amount> [<CUR>] [วันที่ dd/mm] [วงเงินคงเหลือใช้ได้ <balance> THB]"

Notes:
  - the amount ALWAYS has a decimal point, so we anchor on that (this separates
    the amount from digits inside a merchant name like "RAMA 9");
  - currency is optional; when absent it's THB, when present it may be foreign
    (e.g. EUR) — the THB-charged amount isn't in the alert, so we flag it;
  - the trailing "วงเงินคงเหลือใช้ได้ … THB" is the remaining credit line, not the
    amount — stripped before parsing;
  - "ยกเลิก" = the charge was cancelled/reversed → a credit, flagged for review
    until it's netted against the original purchase.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from . import base
from .base import ParsedTxn

_CARD_RE = re.compile(r"UOB-?(\d{4})", re.IGNORECASE)
# @merchant  <amount with required decimal>  [optional 3-letter currency]
_TXN_RE = re.compile(
    r"@\s*(?P<merchant>.+?)\s+(?P<amount>\d{1,3}(?:,\d{3})*\.\d{1,2})\s*(?P<cur>[A-Za-z]{3})?"
)
# remaining credit line printed after the transaction — not the amount
_BALANCE_RE = re.compile(r"วงเงินคงเหลือ.*$")
_CANCEL_RE = re.compile(r"ยกเลิก")


@base.register("UOB")
def parse(title: str, text: str, fallback_ts: datetime) -> Optional[ParsedTxn]:
    norm = base.thai_to_arabic(text)
    body = _BALANCE_RE.sub("", norm)  # drop the available-credit balance
    is_cancel = bool(_CANCEL_RE.search(norm))

    txn = ParsedTxn(
        amount=0.0,
        direction="credit" if is_cancel else "debit",
        method="credit_card",
        bank="UOB",
        ts=base.ensure_tz(fallback_ts),  # date is truncated -> use arrival time
    )

    m = _TXN_RE.search(body)
    if m:
        txn.amount = float(m.group("amount").replace(",", ""))
        merchant = m.group("merchant").strip(" .:-")
        if merchant:
            txn.counterparty_name = merchant
        else:
            txn.flag("UOB: empty merchant")
        cur = (m.group("cur") or "THB").upper()
        if cur != "THB":
            txn.flag(f"UOB: foreign currency {cur} {txn.amount} — THB amount from statement")
    else:
        txn.flag("UOB: could not parse amount/merchant")

    card = _CARD_RE.search(norm)
    if card:
        txn.account_masked = card.group(1)

    if is_cancel:
        # Logged as-is (no auto-netting). As a credit-card credit it naturally
        # reduces the card's outstanding balance (charges - credits).
        txn.note("UOB: cancelled/reversed charge (reduces card balance)")

    return txn
