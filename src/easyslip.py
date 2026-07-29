"""EasySlip integration — verify a Thai bank slip image and get structured data.

Docs: https://document.easyslip.com/th/v2/verify/bank/image
  POST https://api.easyslip.com/v2/verify/bank
  Header: Authorization: Bearer <API_KEY>
  Body:   multipart/form-data, field `image` = the slip image file
  Returns structured JSON (amount, date, sender, receiver, transRef, fee).

This replaces OCR guessing with the bank's own verified data (read from the
slip's QR code), so it's reliable and format-independent.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from . import owner as owner_mod
from .parsers.base import ParsedTxn, ensure_tz

EASYSLIP_URL = "https://api.easyslip.com/v2/verify/bank"

# EasySlip bank short-code / name -> our internal bank code.
BANK_MAP = {
    "KBANK": "KBANK", "KASIKORNBANK": "KBANK", "กสิกรไทย": "KBANK",
    "SCB": "SCB", "ไทยพาณิชย์": "SCB",
    "BBL": "BBL", "กรุงเทพ": "BBL",
    "KTB": "KTB", "กรุงไทย": "KTB",
    "BAY": "BAY", "กรุงศรี": "BAY", "อยุธยา": "BAY",
    "TTB": "TTB", "ทหารไทยธนชาต": "TTB",
    "UOB": "UOB", "ยูโอบี": "UOB",
    "GSB": "GSB", "ออมสิน": "GSB",
    "KKP": "KKP", "CIMB": "CIMB",
}


def verify_image(
    image_bytes: bytes, filename: str, api_key: str, timeout: float = 25.0
) -> tuple[int, dict[str, Any]]:
    """POST the image to EasySlip. Returns (status_code, parsed_json)."""
    import httpx  # bundled via supabase's dependencies

    resp = httpx.post(
        EASYSLIP_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        files={"image": (filename or "slip.jpg", image_bytes)},
        timeout=timeout,
    )
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {"success": False, "error": {"message": resp.text[:200]}}
    return resp.status_code, body


def _bank_code(bank: Optional[dict]) -> Optional[str]:
    if not bank:
        return None
    for key in ("short", "name", "id"):
        val = str(bank.get(key) or "").upper()
        if val in BANK_MAP:
            return BANK_MAP[val]
    name = str(bank.get("name") or "")
    for needle, code in BANK_MAP.items():
        if needle in name:
            return code
    return bank.get("short") or bank.get("name") or None


def _last4(acct: Optional[str]) -> Optional[str]:
    if not acct:
        return None
    digits = re.sub(r"\D", "", acct)
    return digits[-4:] if len(digits) >= 4 else None


def _name(account: Optional[dict]) -> Optional[str]:
    n = (account or {}).get("name") or {}
    return n.get("th") or n.get("en")


def _account_number(account: Optional[dict]) -> Optional[str]:
    a = (account or {}).get("bank") or {}
    return a.get("account")


def parse_easyslip(
    data: dict,
    owner_names: Optional[list[str]],
    fallback_ts: datetime,
    accounts: Optional[list[dict]] = None,
) -> Optional[ParsedTxn]:
    """Map an EasySlip `data` object to a ParsedTxn (a debit on the sender bank)."""
    slip = (data or {}).get("rawSlip") or {}

    amount = ((slip.get("amount") or {}).get("amount"))
    if amount is None:
        amount = data.get("amountInSlip")
    if amount is None:
        return None

    sender = slip.get("sender") or {}
    receiver = slip.get("receiver") or {}
    sender_acct = sender.get("account") or {}
    receiver_acct = receiver.get("account") or {}

    sender_bank = _bank_code(sender.get("bank"))
    recipient_bank = _bank_code(receiver.get("bank"))
    sender_name = _name(sender_acct)
    recipient_name = _name(receiver_acct)

    ts = fallback_ts
    raw_date = slip.get("date")
    if raw_date:
        try:
            ts = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
        except ValueError:
            ts = fallback_ts
    ts = ensure_tz(ts) if ts.tzinfo is None else ts.astimezone(timezone.utc)

    txn = ParsedTxn(
        amount=float(amount),
        direction="debit",
        method="bank",
        bank=sender_bank or "UNKNOWN",
        ts=ts,
        counterparty_name=recipient_name,
        account_masked=_last4(_account_number(sender_acct)),
        counterparty_bank=recipient_bank,
        counterparty_account=_last4(_account_number(receiver_acct)),
    )

    matcher = owner_mod.OwnerMatcher(owner_names or [])
    # Account numbers are the primary internal-transfer signal; pass the raw
    # (possibly masked) account strings so own_account_match can substring-match
    # whatever digits EasySlip reveals against your stored full numbers.
    is_internal, confident = owner_mod.classify_internal(
        matcher,
        accounts,
        sender_name=sender_name,
        sender_bank=sender_bank,
        sender_acct=_account_number(sender_acct),
        recipient_name=recipient_name,
        recipient_bank=recipient_bank,
        recipient_acct=_account_number(receiver_acct),
    )
    if is_internal:
        txn.is_internal = True
        if confident:
            txn.note("easyslip: internal transfer (own accounts)")
        else:
            txn.flag("easyslip: internal transfer suspected — verify")

    if not sender_bank:
        txn.flag("easyslip: sender bank not mapped")
    ref = slip.get("transRef")
    if ref:
        txn.note(f"transRef={ref}")

    return txn
