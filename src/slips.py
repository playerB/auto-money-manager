"""Transfer-slip ingestion: OCR a slip image and parse it to a transaction.

Flow (source='slip' raw_events):
  phone (MacroDroid File-Changed on the slip folder) uploads the image to
  Supabase Storage and inserts a raw_events row -> this module downloads the
  image, OCRs it locally (Tesseract, private), and parses the fields.

Verified against real KBANK (K+) slips. OCR notes:
  - amount / fee / names / bank names / account last-4 read reliably;
  - the reference number and sometimes the date are unreliable -> we dedup on
    amount+time and fall back to the upload time when the date won't parse.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from . import owner as owner_mod
from .parsers import base
from .parsers.base import ParsedTxn

# Thai bank display-name (as printed on slips) -> code.
BANK_NAME_MAP = {
    "กสิกร": "KBANK",
    "ไทยพาณิชย์": "SCB",
    "กรุงเทพ": "BBL",
    "กรุงไทย": "KTB",
    "กรุงศรี": "BAY",
    "อยุธยา": "BAY",
    "ทหารไทยธนชาต": "TTB",
    "ธนชาต": "TTB",
    "ทีเอ็มบี": "TTB",
    "ยูโอบี": "UOB",
    "ออมสิน": "GSB",
    "เกียรตินาคิน": "KKP",
    "ซีไอเอ็มบี": "CIMB",
    "แลนด์": "LH",
    "ไอซีบีซี": "ICBC",
}

_AMOUNT_RE = re.compile(r"([\d,]+\.\d{2})\s*บาท")
# account last-4 printed like "xxx-x-x3341-x" (case/þ varies in OCR)
_ACCT_RE = re.compile(r"(\d{4})-[xX×]")
_NAME_RE = re.compile(r"(?:นาย|นาง|นางสาว|น\.ส\.)\s*([^\n(<>]+)")


def _clean_name(raw: str) -> str:
    """Strip OCR artifacts from a captured name.

    Slip name lines often have a wide layout gap before a decorative icon that
    OCRs to junk (e.g. 'ศุภวิชญ์ ก          J)'). Cut at the first run of 2+
    spaces and drop tokens containing bracket/pipe noise.
    """
    s = re.split(r"\s{2,}", raw.strip())[0]
    toks = [t for t in s.split() if not re.search(r"[()\[\]{}<>|_/\\]", t)]
    # drop a trailing lone Latin letter when the name is otherwise Thai
    if len(toks) > 1 and re.fullmatch(r"[A-Za-z]", toks[-1]) and any(
        re.search(r"[ก-๙]", t) for t in toks[:-1]
    ):
        toks = toks[:-1]
    return " ".join(toks).strip(" .:-")
# "24 ก.ค. 69 00:00"
_DATETIME_RE = re.compile(
    r"(\d{1,2})\s*([ก-๙]{1,3}\.[ก-๙]?\.?)\s*(\d{2})\s+(\d{1,2}):(\d{2})"
)


# --- Album registry ---------------------------------------------------------
# A slip event's source is "gallery-<album>"; one album = one bank = one slip
# style. Map the album to a bank hint and (later) a style-specific parser.
ALBUM_BANK = {
    "kplus": "KBANK",
}


def bank_for_album(album: Optional[str]) -> Optional[str]:
    return ALBUM_BANK.get((album or "").lower())


def parser_for_album(album: Optional[str]):
    """Return the parse function for an album's slip style.

    Today every album uses the generic `parse_slip` (it reads the banks from the
    slip content). When a bank's slip layout diverges, register a dedicated
    parser here keyed by album.
    """
    return parse_slip


def ocr_image(image_bytes: bytes) -> str:
    """OCR an image (Thai+English). Imported lazily so tests don't need it."""
    import io

    import pytesseract
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(img, lang="tha+eng")


def _banks_in_order(text: str) -> list[str]:
    hits: list[tuple[int, str]] = []
    for name, code in BANK_NAME_MAP.items():
        pos = text.find(name)
        if pos != -1:
            hits.append((pos, code))
    hits.sort()
    # de-dup consecutive identical codes while preserving order
    out: list[str] = []
    for _, code in hits:
        if not out or out[-1] != code:
            out.append(code)
    return out


def _parse_datetime(text: str, fallback: datetime) -> tuple[datetime, bool]:
    m = _DATETIME_RE.search(base.thai_to_arabic(text))
    if m and m.group(2) in base.THAI_MONTHS:
        day = int(m.group(1))
        month = base.THAI_MONTHS[m.group(2)]
        year = base.be2_to_ce(int(m.group(3)))
        try:
            return base.build_local_dt(year, month, day, int(m.group(4)), int(m.group(5))), True
        except ValueError:
            pass
    return base.ensure_tz(fallback), False


def parse_slip(
    ocr_text: str,
    fallback_ts: datetime,
    owner_names: Optional[list[str]] = None,
    folder_bank: Optional[str] = None,
) -> Optional[ParsedTxn]:
    """Parse a transfer slip's OCR text into a (debit) transaction.

    A transfer slip documents money leaving the sender (top party) toward the
    recipient (bottom party). We record it as a debit on the sender's bank.
    It's an internal transfer only when BOTH sender and recipient are the owner.
    """
    matcher = owner_mod.OwnerMatcher(owner_names or [])
    text = base.thai_to_arabic(ocr_text)

    amounts = _AMOUNT_RE.findall(text)
    if not amounts:
        return None  # not a recognizable slip
    amount = float(amounts[0].replace(",", ""))

    accts = _ACCT_RE.findall(text)
    names = [_clean_name(n) for n in _NAME_RE.findall(ocr_text)]
    names = [n for n in names if n]
    banks = _banks_in_order(text)

    sender_bank = banks[0] if banks else (folder_bank or "")
    recipient_bank = banks[1] if len(banks) > 1 else None
    sender_acct = accts[0] if accts else None
    recipient_acct = accts[1] if len(accts) > 1 else None
    sender_name = names[0] if names else None
    recipient_name = names[1] if len(names) > 1 else None

    ts, ts_ok = _parse_datetime(ocr_text, fallback_ts)

    txn = ParsedTxn(
        amount=amount,
        direction="debit",
        method="bank",
        bank=sender_bank or "UNKNOWN",
        ts=ts,
        counterparty_name=recipient_name,
        account_masked=sender_acct,
        counterparty_bank=recipient_bank,
        counterparty_account=recipient_acct,
    )

    # Internal transfer: BOTH sender and recipient must be the owner.
    is_internal, confident = owner_mod.classify_transfer(
        matcher, sender_name, recipient_name
    )
    if is_internal:
        txn.is_internal = True
        if confident:
            txn.note("slip: internal transfer (own accounts)")
        else:
            txn.flag("slip: internal transfer suspected but names redacted — verify")

    if not sender_bank:
        txn.flag("slip: sender bank not identified")
    if not ts_ok:
        txn.note("slip: date fell back to upload time")

    return txn
