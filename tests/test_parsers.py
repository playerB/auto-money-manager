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


def test_scb_outgoing():
    # Real outgoing payload (LINE truncated the date to "24/0").
    t = d("SCB", "SCB Connect", "รายการเงินออก 4.00 บาท จากบัญชี X-6442 วันที่ 24/0")
    assert t.bank == "SCB"
    assert t.direction == "debit"
    assert t.amount == 4.00
    assert t.account_masked == "6442"
    assert t.ts == FB  # truncated date -> arrival time
    assert not t.needs_review  # direction + amount known; ts fallback is only a note


def test_scb_truncated_falls_back():
    t = d("SCB", "SCB Connect", "รายการเงินเข้า 5.00 บาท เข้าบัญชี X-6442 วันที่ 24")
    assert t.amount == 5.00
    assert t.account_masked == "6442"
    assert t.ts == FB  # truncated date -> arrival time
    assert not t.needs_review  # ts fallback is a note, not a review flag


# --- UOB card (via LINE) — real samples --------------------------------------
def test_uob_purchase_no_currency():
    t = d("UOB", "UOB Thai", "มีการใช้บัตร UOB-1640 @WWW.GRAB.COM 29.00")
    assert t.bank == "UOB" and t.method == "credit_card"
    assert t.direction == "debit"
    assert t.amount == 29.00
    assert t.account_masked == "1640"
    assert t.counterparty_name == "WWW.GRAB.COM"
    assert not t.needs_review


def test_uob_purchase_ignores_balance():
    t = d(
        "UOB", "UOB Thai",
        "มีการใช้บัตร UOB-8340 @(FOR SHOPEE)*(FOR SHOP 1,336.00 THB วันที่ 24/05 "
        "วงเงินคงเหลือใช้ได้ 133,071.00 THB",
    )
    assert t.amount == 1336.00  # NOT the 133,071.00 balance
    assert t.account_masked == "8340"
    assert t.counterparty_name == "(FOR SHOPEE)*(FOR SHOP"
    assert t.direction == "debit"


def test_uob_merchant_with_digits():
    t = d("UOB", "UOB Thai", "มีการใช้บัตร UOB-1640 @MITSUKOSHI DEPACHIKA 79.00 THB วันที่ 27/07 ")
    assert t.amount == 79.00
    assert t.counterparty_name == "MITSUKOSHI DEPACHIKA"


def test_uob_foreign_currency_flagged():
    t = d(
        "UOB", "UOB Thai",
        "มีการใช้บัตร UOB-9762 @TRENITALIA - LEFRECCE 14.8 EUR วันที่ 24/05 "
        "วงเงินคงเหลือใช้ได้ 134,407.00 THB",
    )
    assert t.amount == 14.8
    assert t.counterparty_name == "TRENITALIA - LEFRECCE"
    assert t.needs_review  # foreign currency -> THB amount comes from statement


def test_uob_cancellation_is_credit():
    t = d("UOB", "UOB Thai", "มีการยกเลิกทำรายการบัตร UOB-1640 @KAMIKA-CENTRAL RAMA 9 399.00 THB")
    assert t.direction == "credit"
    assert t.amount == 399.00  # not the "9" in the merchant name
    assert t.counterparty_name == "KAMIKA-CENTRAL RAMA 9"
    assert t.needs_review  # reversal -> verify netting


def test_uob_cancellation_ignores_balance():
    t = d(
        "UOB", "UOB Thai",
        "มีการยกเลิกทำรายการบัตร UOB-8340 @(FOR SHOPEE)*(FOR SHOP 665.00 THB วันที่  30/12 "
        "วงเงินคงเหลือใช้ได้ 19,061.00 THB",
    )
    assert t.direction == "credit"
    assert t.amount == 665.00
    assert t.account_masked == "8340"


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
