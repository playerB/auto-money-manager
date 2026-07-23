"""SCB parser — notifications arrive via LINE (sender 'SCB Connect').

Samples (redacted):
    text: "รายการเงินเข้า 1.00 บาท เข้าบัญชี X-6442 วันที่ 23/07/2026 @23:44 ยอดเงินที่ใช้ได้ 57,554.73 บาท"
    text: "รายการเงินเข้า 5.00 บาท เข้าบัญชี X-6442 วันที่ 24"   (LINE truncated the rest)

Notes:
  - the FIRST amount is the transaction; the trailing "ยอดเงินที่ใช้ได้" is the
    available balance and must be ignored.
  - LINE truncates long messages, so date/time may be missing -> fall back to
    arrival time.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from . import base
from .base import ParsedTxn

# First "<amount> บาท" only (avoid the later balance figure).
_AMOUNT_RE = re.compile(r"([\d,]+\.\d{2})\s*บาท")
_ACCOUNT_RE = re.compile(r"บัญชี\s*[xX]-?(\d{4})")
_DATE_RE = re.compile(r"วันที่\s*(\d{1,2})/(\d{1,2})/(\d{4})")
_TIME_RE = re.compile(r"@\s*(\d{1,2}):(\d{2})")

# Strip the balance clause before amount parsing, just to be safe.
_BALANCE_RE = re.compile(r"ยอดเงินที่ใช้ได้.*$")


def _direction(text: str) -> Optional[str]:
    if "เงินเข้า" in text or "รับ" in text:
        return "credit"
    if "โอน" in text or "ถอน" in text or "ชำระ" in text or "ใช้จ่าย" in text:
        return "debit"
    return None


def _timestamp(text: str, fallback: datetime) -> tuple[datetime, bool]:
    text = base.thai_to_arabic(text)
    dm = _DATE_RE.search(text)
    tm = _TIME_RE.search(text)
    if dm:
        day, month, year = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        try:
            return base.build_local_dt(year, month, day, hour, minute), True
        except ValueError:
            pass
    return base.ensure_tz(fallback), False


@base.register("SCB")
def parse(title: str, text: str, fallback_ts: datetime) -> Optional[ParsedTxn]:
    norm = base.thai_to_arabic(text)
    amount_src = _BALANCE_RE.sub("", norm)  # drop balance clause

    ts, ts_ok = _timestamp(norm, fallback_ts)
    txn = ParsedTxn(
        amount=0.0,
        direction=_direction(norm) or "debit",
        method="bank",
        bank="SCB",
        ts=ts,
    )

    am = _AMOUNT_RE.search(amount_src)
    if am:
        txn.amount = float(am.group(1).replace(",", ""))
    else:
        txn.flag("SCB: no amount parsed")

    acc = _ACCOUNT_RE.search(norm)
    if acc:
        txn.account_masked = acc.group(1)

    if _direction(norm) is None:
        txn.flag("SCB: direction defaulted to debit")
    if not ts_ok:
        txn.flag("SCB: timestamp fell back to arrival time (message truncated?)")

    return txn
