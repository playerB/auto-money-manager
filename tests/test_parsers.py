"""Parser tests using the real (redacted) notification payloads.

Router: payload['app'] selects the bank parser (KBANK / SCB / UOB).
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.dedup import build_dedup_key
from src.parsers import dispatch

# Fallback arrival time used when a message's own timestamp is missing/truncated.
FB = datetime(2026, 7, 23, 17, 0, tzinfo=timezone.utc)


def d(app, title, text):
    return dispatch({"app": app, "title": title, "text": text}, FB)


# --- KBANK (direct app) ------------------------------------------------------
def test_kbank_incoming():
    t = d("KBANK", "รายการเงินเข้า",
          "บัญชี xxx-x-x3341-x  จำนวนเงิน 2.00 บาท  วันที่ 23 ก.ค. 69  23:49 น.")
    assert t is not None
    assert t.bank == "KBANK" and t.method == "bank"
    assert t.direction == "credit"
    assert t.amount == 2.00
    assert t.account_masked == "3341"
    # 23 Jul 2569 BE 23:49 (+07:00) -> 16:49 UTC
    assert t.ts == datetime(2026, 7, 23, 16, 49, tzinfo=timezone.utc)
    assert not t.needs_review


def test_kbank_transfer_out():
    t = d("KBANK", "รายการโอน/ถอน",
          "บัญชี xxx-x-x3341-x  จำนวนเงิน 3.00 บาท  วันที่ 23 ก.ค. 69  23:55 น.")
    assert t.direction == "debit"
    assert t.amount == 3.00
    assert t.ts == datetime(2026, 7, 23, 16, 55, tzinfo=timezone.utc)


# --- SCB (via LINE) ----------------------------------------------------------
def test_scb_incoming_ignores_balance():
    t = d("SCB", "SCB Connect",
          "รายการเงินเข้า 1.00 บาท เข้าบัญชี X-6442 วันที่ 23/07/2026 @23:44 "
          "ยอดเงินที่ใช้ได้ 57,554.73 บาท")
    assert t.bank == "SCB"
    assert t.direction == "credit"
    assert t.amount == 1.00  # NOT the 57,554.73 balance
    assert t.account_masked == "6442"
    assert t.ts == datetime(2026, 7, 23, 16, 44, tzinfo=timezone.utc)
    assert not t.needs_review


def test_scb_truncated_falls_back():
    t = d("SCB", "SCB Connect", "รายการเงินเข้า 5.00 บาท เข้าบัญชี X-6442 วันที่ 24")
    assert t.amount == 5.00
    assert t.account_masked == "6442"
    assert t.ts == FB  # truncated date -> arrival time
    assert t.needs_review  # flagged that the timestamp was a fallback


# --- UOB card (via LINE) -----------------------------------------------------
def test_uob_card_purchase():
    t = d("UOB", "UOB Thai", "มีการใช้บัตร UOB-8340 @TMN 7-11 1.00 THB วันที่ 23")
    assert t.bank == "UOB" and t.method == "credit_card"
    assert t.direction == "debit"
    assert t.amount == 1.00
    assert t.account_masked == "8340"
    assert t.counterparty_name == "TMN 7-11"
    assert t.ts == FB  # day-only date -> arrival time
    assert not t.is_internal


# --- routing + dedup ---------------------------------------------------------
def test_unknown_app_returns_none():
    assert d("RANDOMBANK", "x", "y") is None


def test_two_same_amount_kbank_are_distinct():
    a = d("KBANK", "รายการเงินเข้า",
          "บัญชี xxx-x-x3341-x  จำนวนเงิน 2.00 บาท  วันที่ 23 ก.ค. 69  23:49 น.")
    b = d("KBANK", "รายการเงินเข้า",
          "บัญชี xxx-x-x3341-x  จำนวนเงิน 2.00 บาท  วันที่ 23 ก.ค. 69  23:57 น.")
    # Different minute -> different dedup key -> both kept (not merged).
    assert build_dedup_key(a) != build_dedup_key(b)
