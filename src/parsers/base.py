"""Shared parsing utilities and the parser dispatcher."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from zoneinfo import ZoneInfo

from .. import config

# --- Thai numeral handling ---------------------------------------------------
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def thai_to_arabic(s: str) -> str:
    return s.translate(_THAI_DIGITS)


# Money amount like 1,234.56 or 1234 or ๑,๒๓๔.๕๖
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)")


def parse_amount(text: str) -> Optional[float]:
    """Pull the most likely money amount from a string.

    Heuristic: prefer a number that appears near a currency marker
    (บาท / ฿ / THB); otherwise fall back to the largest number found.
    """
    text = thai_to_arabic(text)
    # Prefer amounts adjacent to a currency marker.
    near = re.findall(
        r"(?:฿|THB\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:บาท|฿|THB)?",
        text,
    )
    candidates = [c for c in near if re.search(r"\d", c)]
    if not candidates:
        candidates = _AMOUNT_RE.findall(text)
    if not candidates:
        return None
    values = [float(c.replace(",", "")) for c in candidates]
    # Currency amounts almost always have decimals or are the largest token.
    with_decimals = [v for v, c in zip(values, candidates) if "." in c]
    return max(with_decimals) if with_decimals else max(values)


# Account / card last-4 like x1234, xxxx1234, *1234, ...1234
_LAST4_RE = re.compile(r"(?:x|X|\*|xxxx|XXXX|\.{2,})\s?(\d{4})")


def parse_last4(text: str) -> Optional[str]:
    text = thai_to_arabic(text)
    m = _LAST4_RE.search(text)
    return m.group(1) if m else None


def local_now() -> datetime:
    return datetime.now(ZoneInfo(config.LOCAL_TZ))


def ensure_tz(dt: datetime) -> datetime:
    """Attach the configured local tz if naive, then convert to UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(config.LOCAL_TZ))
    return dt.astimezone(timezone.utc)


@dataclass
class ParsedTxn:
    amount: float
    direction: str  # 'debit' (money out) | 'credit' (money in)
    method: str  # 'bank' | 'credit_card' | 'cash'
    bank: str  # 'KBANK' | 'UOB' | ...
    ts: datetime
    counterparty_name: Optional[str] = None
    account_masked: Optional[str] = None
    is_internal: bool = False
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)

    def flag(self, reason: str) -> None:
        self.needs_review = True
        self.review_reasons.append(reason)


# --- Direction keywords (Thai + English) ------------------------------------
DEBIT_WORDS = [
    "โอนออก", "โอนเงิน", "ชำระ", "จ่าย", "ถอน", "ซื้อ", "หักบัญชี",
    "ใช้จ่าย", "เติมเงิน", "payment", "paid", "purchase", "withdraw", "debit",
]
CREDIT_WORDS = [
    "รับโอน", "เงินเข้า", "รับเงิน", "โอนเข้า", "ฝาก", "คืนเงิน",
    "received", "deposit", "refund", "credit",
]


def guess_direction(text: str) -> Optional[str]:
    low = text.lower()
    # Check credit first: "รับโอน" contains "โอน" which also appears in debit words.
    if any(w.lower() in low for w in CREDIT_WORDS):
        return "credit"
    if any(w.lower() in low for w in DEBIT_WORDS):
        return "debit"
    return None


# --- Parser registry ---------------------------------------------------------
# Each parser: (title, text, ts_hint) -> Optional[ParsedTxn]
ParserFn = Callable[[str, str, datetime], Optional["ParsedTxn"]]
_REGISTRY: list[ParserFn] = []


def register(fn: ParserFn) -> ParserFn:
    _REGISTRY.append(fn)
    return fn


def dispatch(payload: dict) -> Optional[ParsedTxn]:
    """Run each registered parser until one recognizes the message.

    payload keys (from MacroDroid / phone): title, text, timestamp (optional,
    epoch seconds or ISO string).
    """
    title = str(payload.get("title", "") or "")
    text = str(payload.get("text", "") or "")
    ts_hint = _coerce_ts(payload.get("timestamp"))
    for fn in _REGISTRY:
        result = fn(title, text, ts_hint)
        if result is not None:
            return result
    return None


def _coerce_ts(raw) -> datetime:
    if raw is None or raw == "":
        return local_now()
    try:
        # epoch seconds (or ms)
        num = float(raw)
        if num > 1e12:  # milliseconds
            num /= 1000.0
        return datetime.fromtimestamp(num, tz=timezone.utc)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return local_now()


# Import concrete parsers so they self-register. Placed at the bottom to avoid
# circular imports.
from . import kbank as _kbank  # noqa: E402,F401
from . import uob as _uob  # noqa: E402,F401
