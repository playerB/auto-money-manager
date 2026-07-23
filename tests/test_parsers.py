"""Parser tests using illustrative (redacted) sample notifications.

These samples are placeholders that match the current best-effort patterns.
Replace them with 2-3 real redacted notifications and adjust as needed — the
tests then lock the real formats in place.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.dedup import build_dedup_key
from src.parsers import dispatch
from src.parsers.base import guess_direction, parse_amount, parse_last4

TS = datetime(2026, 7, 23, 10, 30, tzinfo=timezone.utc)


def _payload(title, text):
    return {"title": title, "text": text, "timestamp": TS.isoformat()}


# --- utility functions -------------------------------------------------------
def test_parse_amount_with_currency():
    assert parse_amount("โอนเงิน 1,500.00 บาท") == 1500.00
    assert parse_amount("spent THB 1,299.00 at LAZADA") == 1299.00
    assert parse_amount("no money here") is None


def test_parse_amount_thai_digits():
    assert parse_amount("จำนวน ๓๕๐.๐๐ บาท") == 350.00


def test_parse_last4():
    assert parse_last4("บัญชี x1234") == "1234"
    assert parse_last4("UOB Card xxxx5678") == "5678"


def test_guess_direction():
    assert guess_direction("รับโอน 2,000 บาท") == "credit"
    assert guess_direction("โอนเงิน 500 บาท") == "debit"
    assert guess_direction("hello") is None


# --- KBANK -------------------------------------------------------------------
def test_kbank_outgoing_transfer():
    txn = dispatch(
        _payload("KBANK", "โอนเงิน 1,500.00 บาท จากบัญชี x1234 ไปยัง นายสมชาย ใจดี")
    )
    assert txn is not None
    assert txn.bank == "KBANK"
    assert txn.method == "bank"
    assert txn.direction == "debit"
    assert txn.amount == 1500.00
    assert txn.account_masked == "1234"
    assert "สมชาย" in (txn.counterparty_name or "")


def test_kbank_incoming_transfer():
    txn = dispatch(_payload("KBANK", "รับโอน 2,000.00 บาท เข้าบัญชี x1234"))
    assert txn is not None
    assert txn.direction == "credit"
    assert txn.amount == 2000.00


# --- UOB ---------------------------------------------------------------------
def test_uob_card_purchase():
    txn = dispatch(
        _payload("UOB", "UOB Card xxxx1234 spent THB 1,299.00 at LAZADA")
    )
    assert txn is not None
    assert txn.bank == "UOB"
    assert txn.method == "credit_card"
    assert txn.direction == "debit"
    assert txn.amount == 1299.00
    assert txn.account_masked == "1234"
    assert not txn.is_internal


def test_uob_card_payment_is_internal():
    txn = dispatch(_payload("UOB", "ชำระยอดบัตรเครดิต 5,000.00 บาท"))
    assert txn is not None
    assert txn.is_internal is True


# --- dispatch + dedup --------------------------------------------------------
def test_unknown_message_returns_none():
    assert dispatch(_payload("SomeApp", "hello world")) is None


def test_dedup_key_stable_and_distinct():
    a = dispatch(_payload("KBANK", "โอนเงิน 1,500.00 บาท จากบัญชี x1234 ไปยัง นายสมชาย"))
    b = dispatch(_payload("KBANK", "โอนเงิน 1,500.00 บาท จากบัญชี x1234 ไปยัง นายสมชาย"))
    c = dispatch(_payload("KBANK", "โอนเงิน 1,600.00 บาท จากบัญชี x1234 ไปยัง นายสมชาย"))
    assert build_dedup_key(a) == build_dedup_key(b)  # same txn -> same key
    assert build_dedup_key(a) != build_dedup_key(c)  # different amount -> different
