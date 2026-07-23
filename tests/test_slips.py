"""Slip parser tests using the real OCR output from KBANK (K+) slips."""
from __future__ import annotations

from datetime import datetime, timezone

from src.owner import OwnerMatcher, classify_transfer
from src.slips import parse_slip

# Full owner names (Thai + English), as they'd be configured via OWNER_NAMES.
OWNER = ["นาย ศุภวิชญ์ กนกพงศกร", "SUPAWISH KANOKPONGSAKORN"]
FB = datetime(2026, 7, 24, 5, 0, tzinfo=timezone.utc)

# Real Tesseract (tha+eng) output from a 5.00-baht KBANK slip (date parsed OK).
OCR_5BAHT = """โอนเงินสําเร็จ

24 ก.ค. 69 00:00น. K+

นาย ศุภวิชญ์ ก
ธ.กสิกรไทย
XXX-X-X3341-x

นาย ศุภวิชญ์ กนกพงศกร
ธ.ไทยพาณิชย์
XXX-X-x7644-x

เลขที่รายการ:
016205000018808004732
จํานวน:
5.00 บาท
ค่าธรรมเนียม:
0.00 บาท   สแกนตรวจสอบสลิป
"""

# Real output from a 1.00-baht slip where the date line was garbled by OCR.
OCR_1BAHT = """โอนเงินสําเร็จ

Benn eo 34d K+

นาย ศุภวิชญ์ ก
ธ.กสิกรไทย
XXX-X-X3341-x

นาย ศุภวิชญ์ กนกพงศกร
ธ.ไทยพาณิชย์
XXX-X-X7644-x

เลขทีรายการ:
016204234455A0R03910
จํานวน:
1.00 บาท
ค่าธรรมเนียม:
0.00 บาท   สแกนตรวจสอบสลิป
"""


def test_slip_amount_not_fee():
    t = parse_slip(OCR_5BAHT, FB, OWNER)
    assert t is not None
    assert t.amount == 5.00  # the จำนวน amount, not the 0.00 fee


def test_slip_sender_and_recipient():
    t = parse_slip(OCR_5BAHT, FB, OWNER)
    assert t.bank == "KBANK"  # sender bank
    assert t.account_masked == "3341"
    assert t.counterparty_bank == "SCB"  # recipient bank
    assert t.counterparty_account == "7644"
    assert "กนกพงศกร" in (t.counterparty_name or "")


def test_slip_direction_and_internal():
    t = parse_slip(OCR_5BAHT, FB, OWNER)
    assert t.direction == "debit"
    assert t.is_internal is True  # both parties are the owner


def test_slip_date_parsed_when_clean():
    t = parse_slip(OCR_5BAHT, FB, OWNER)
    # 24 ก.ค. 2569 BE 00:00 (+07:00) -> 2026-07-23 17:00 UTC
    assert t.ts == datetime(2026, 7, 23, 17, 0, tzinfo=timezone.utc)
    assert not t.needs_review


def test_slip_date_fallback_when_garbled():
    t = parse_slip(OCR_1BAHT, FB, OWNER)
    assert t.amount == 1.00
    assert t.ts == FB  # garbled date -> upload time
    assert not t.needs_review  # fallback is a note, not a review flag


def test_slip_not_internal_without_owner_config():
    # If we don't know the owner, it shouldn't be flagged internal.
    t = parse_slip(OCR_5BAHT, FB, owner_names=[])
    assert t.is_internal is False


def test_non_slip_text_returns_none():
    assert parse_slip("just some random text with no amount", FB, OWNER) is None


# --- owner matcher: redaction, abbreviation, Thai/English, friend safety -----
M = OwnerMatcher(OWNER)


def test_owner_matches_redacted_and_abbreviated_forms():
    for name in [
        "นาย ศุภวิชญ์",            # first name only (weak)
        "นาย ศุภวิชญ์ ก.",         # surname initial with dot
        "นาย ศุภวิชญ์ ก",          # surname initial
        "ศุภวิชญ์ ก***",           # redacted surname
        "นาย ศุภวิชญ์ กนกพงศกร",   # full Thai
        "SUPAWISH KANO",           # truncated English surname
        "SUPAWISH KANOKPONGSAKORN",  # full English
    ]:
        ok, _strong = M.match(name)
        assert ok, name


def test_owner_strength():
    assert M.match("นาย ศุภวิชญ์ กนกพงศกร") == (True, True)   # full -> strong
    assert M.match("นาย ศุภวิชญ์ ก") == (True, False)         # initial -> weak
    assert M.match("SUPAWISH KANO") == (True, True)          # 4 chars -> strong


def test_friend_with_similar_first_name_is_not_owner():
    # Same first name, different surname -> NOT the owner.
    ok, _ = M.match("นาย ศุภวิชญ์ ธนวัฒน์")
    assert ok is False


def test_internal_requires_both_parties():
    # Owner -> friend is NOT internal (recipient isn't owner).
    is_int, _ = classify_transfer(M, "ศุภวิชญ์ ก", "นาย สมชาย ใจดี")
    assert is_int is False
    # Owner (redacted sender) -> owner (full recipient) IS internal & confident.
    is_int, confident = classify_transfer(M, "ศุภวิชญ์ ก", "ศุภวิชญ์ กนกพงศกร")
    assert is_int is True and confident is True


def test_internal_survives_ocr_junk_on_sender_name():
    # Real regression: OCR appended 'J)' after the redacted sender surname.
    ocr = OCR_5BAHT.replace("นาย ศุภวิชญ์ ก\n", "นาย ศุภวิชญ์ ก          J)\n")
    t = parse_slip(ocr, FB, OWNER)
    assert t.is_internal is True


def test_internal_both_redacted_is_flagged_for_review():
    t = parse_slip(
        OCR_5BAHT.replace("ศุภวิชญ์ กนกพงศกร", "ศุภวิชญ์ ก***"), FB, OWNER
    )
    assert t.is_internal is True
    assert t.needs_review is True  # both sides redacted -> verify
