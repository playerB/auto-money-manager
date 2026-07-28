"""Tests for the UOB credit-card bill-payment slip parser.

Uses the real Tesseract OCR output from three UOB/TMRW payment slips (note "THB"
sometimes OCRs as "1118" — the parser anchors on the decimal amount, not "THB").
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.slips import parse_uob_payment

FB = datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc)

OCR_1640 = """หมายเลขอ้างอิง 2607075865216353   TMRW
1118 926.59
ฟรีค่าธรรมเนียม
นาย ศุภวิชญ์ กนกพงศกร
NEW V CARE
XXX XXX 529 1
ยูโอบี/ มาสเตอร์ คาร์ด
5432 1561 0042 1640
07 Jul 2026
03:08 PM
จ่ายบิล
"""

OCR_8340 = """หมายเลขอ้างอิง 2607075865212148
THB 13,008.75
ยูโอบี/ มาสเตอร์ คาร์ด
5432 1580 0039 8340
07 Jul 2026
03:07 PM
จ่ายบิล
"""

OCR_9762 = """หมายเลขอ้างอิง 2607075865139354
1118 95,681.18
ยูโอบี/ มาสเตอร์ คาร์ด
5257 2060 0126 9762
07 Jul 2026
02:51 PM
จ่ายบิล
"""


def test_payment_amount_and_card_1640():
    t = parse_uob_payment(OCR_1640, FB)
    assert t is not None
    assert t.bank == "UOB" and t.method == "credit_card"
    assert t.direction == "credit"  # reduces card outstanding
    assert t.amount == 926.59  # not the "1118" OCR of THB
    assert t.account_masked == "1640"
    assert not t.needs_review


def test_payment_amount_with_thousands_8340():
    t = parse_uob_payment(OCR_8340, FB)
    assert t.amount == 13008.75
    assert t.account_masked == "8340"


def test_payment_large_amount_9762():
    t = parse_uob_payment(OCR_9762, FB)
    assert t.amount == 95681.18
    assert t.account_masked == "9762"


def test_payment_real_timestamp():
    t = parse_uob_payment(OCR_1640, FB)
    # 07 Jul 2026 03:08 PM +07:00 -> 08:08 UTC
    assert t.ts == datetime(2026, 7, 7, 8, 8, tzinfo=timezone.utc)


def test_not_a_payment_returns_none():
    assert parse_uob_payment("random text, no amount", FB) is None
