"""Shared parsing utilities and the parser dispatcher.

Routing: the phone sets payload["app"] to the bank code (KBANK / SCB / UOB),
so dispatch is a reliable lookup rather than keyword sniffing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from zoneinfo import ZoneInfo

from .. import config

# --- Thai numerals -----------------------------------------------------------
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def thai_to_arabic(s: str) -> str:
    return s.translate(_THAI_DIGITS)


# --- Thai month abbreviations (as they appear in KBANK alerts) ---------------
THAI_MONTHS = {
    "ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3, "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
    "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9, "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12,
}


def be2_to_ce(yy: int) -> int:
    """2-digit Buddhist-era year -> Gregorian year. 69 -> 2569 BE -> 2026 CE."""
    return 2500 + yy - 543


# --- Generic amount helper (used by tests / fallback) ------------------------
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)")


def first_amount(text: str) -> Optional[float]:
    """First money-like number in the string (left to right).

    Important: banks often include a running balance later in the message, so
    the FIRST amount (nearest the action) is the transaction amount.
    """
    text = thai_to_arabic(text)
    m = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2}))", text)
    if m:
        return float(m.group(1).replace(",", ""))
    m = _AMOUNT_RE.search(text)
    return float(m.group(1).replace(",", "")) if m else None


def local_now() -> datetime:
    return datetime.now(ZoneInfo(config.LOCAL_TZ))


def ensure_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(config.LOCAL_TZ))
    return dt.astimezone(timezone.utc)


def build_local_dt(y: int, mo: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return ensure_tz(datetime(y, mo, d, h, mi))


@dataclass
class ParsedTxn:
    amount: float
    direction: str  # 'debit' (out) | 'credit' (in)
    method: str  # 'bank' | 'credit_card' | 'cash'
    bank: str  # 'KBANK' | 'SCB' | 'UOB'
    ts: datetime
    counterparty_name: Optional[str] = None
    account_masked: Optional[str] = None
    is_internal: bool = False
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)

    def flag(self, reason: str) -> None:
        """Material uncertainty (missing amount/direction) -> needs review."""
        self.needs_review = True
        self.review_reasons.append(reason)

    def note(self, reason: str) -> None:
        """Informational note (e.g. timestamp fallback) -> recorded, not flagged."""
        self.review_reasons.append(reason)


# --- Parser registry, keyed by bank code ------------------------------------
ParserFn = Callable[[str, str, datetime], Optional["ParsedTxn"]]
_PARSERS: dict[str, ParserFn] = {}


def register(bank_code: str) -> Callable[[ParserFn], ParserFn]:
    def deco(fn: ParserFn) -> ParserFn:
        _PARSERS[bank_code.upper()] = fn
        return fn

    return deco


def dispatch(payload: dict, fallback_ts: Optional[datetime] = None) -> Optional[ParsedTxn]:
    """Route a raw notification to its bank parser via payload['app'].

    payload keys from the phone: app, title, text.
    fallback_ts: arrival time (raw_events.received_at) used when the message's
    own timestamp is missing or truncated (LINE cuts long notifications off).
    """
    app = str(payload.get("app", "") or "").strip().upper()
    title = str(payload.get("title", "") or "")
    text = str(payload.get("text", "") or "")
    fb = fallback_ts or local_now()
    fn = _PARSERS.get(app)
    if fn is None:
        return None
    return fn(title, text, fb)


# Import concrete parsers so they self-register (bottom to avoid cycles).
from . import kbank as _kbank  # noqa: E402,F401
from . import scb as _scb  # noqa: E402,F401
from . import uob as _uob  # noqa: E402,F401
