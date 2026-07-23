"""KBANK parser — notifications come straight from the KBANK app (reliable).

Samples (redacted):
    title: "รายการเงินเข้า"      text: "บัญชี xxx-x-x3341-x  จำนวนเงิน 2.00 บาท  วันที่ 23 ก.ค. 69  23:49 น."
    title: "รายการโอน/ถอน"       text: "บัญชี xxx-x-x3341-x  จำนวนเงิน 3.00 บาท  วันที่ 23 ก.ค. 69  23:55 น."

KBANK app alerts carry account + amount + date/time, but no counterparty name.
Direction comes from the title.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from . import base
from .base import ParsedTxn

_AMOUNT_RE = re.compile(r"จำนวนเงิน\s*([\d,]+\.\d{2})")
_ACCOUNT_RE = re.compile(r"บัญชี\s*([xX0-9\-]+)")
# "วันที่ 23 ก.ค. 69" then "23:49 น."
_DATE_RE = re.compile(r"วันที่\s*(\d{1,2})\s*([ก-๙]+\.[ก-๙]+\.)\s*(\d{2})")
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*น\.")


def _direction(title: str, text: str) -> Optional[str]:
    blob = f"{title} {text}"
    if "เงินเข้า" in blob:
        return "credit"
    if "โอน" in blob or "ถอน" in blob or "ชำระ" in blob:
        return "debit"
    return None


def _timestamp(text: str, fallback: datetime) -> tuple[datetime, bool]:
    text = base.thai_to_arabic(text)
    dm = _DATE_RE.search(text)
    tm = _TIME_RE.search(text)
    if dm and dm.group(2) in base.THAI_MONTHS:
        day = int(dm.group(1))
        month = base.THAI_MONTHS[dm.group(2)]
        year = base.be2_to_ce(int(dm.group(3)))
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        try:
            return base.build_local_dt(year, month, day, hour, minute), True
        except ValueError:
            pass
    return base.ensure_tz(fallback), False


@base.register("KBANK")
def parse(title: str, text: str, fallback_ts: datetime) -> Optional[ParsedTxn]:
    ts, ts_ok = _timestamp(text, fallback_ts)
    txn = ParsedTxn(
        amount=0.0,
        direction=_direction(title, text) or "debit",
        method="bank",
        bank="KBANK",
        ts=ts,
    )

    am = _AMOUNT_RE.search(base.thai_to_arabic(text))
    if am:
        txn.amount = float(am.group(1).replace(",", ""))
    else:
        txn.flag("KBANK: no amount parsed")

    acc = _ACCOUNT_RE.search(text)
    if acc:
        digits = re.sub(r"\D", "", base.thai_to_arabic(acc.group(1)))
        if len(digits) >= 4:
            txn.account_masked = digits[-4:]

    if _direction(title, text) is None:
        txn.flag("KBANK: direction defaulted to debit")
    if not ts_ok:
        txn.flag("KBANK: timestamp fell back to arrival time")

    return txn
