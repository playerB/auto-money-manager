"""Tests for mapping an EasySlip response to a transaction."""
from __future__ import annotations

from datetime import datetime, timezone

from src.easyslip import parse_easyslip

OWNER = ["นาย ศุภวิชญ์ กนกพงศกร", "SUPAWISH KANOKPONGSAKORN"]
FB = datetime(2026, 7, 26, 0, 0, tzinfo=timezone.utc)

# Representative EasySlip `data` object for an own KBANK -> own SCB transfer.
DATA = {
    "isDuplicate": False,
    "amountInSlip": 1.00,
    "rawSlip": {
        "transRef": "016207022505AOR09159",
        "date": "2026-07-25T19:25:00+07:00",
        "amount": {"amount": 1.00, "local": {"amount": 1.00, "currency": "THB"}},
        "fee": 0.00,
        "sender": {
            "bank": {"id": "004", "name": "KASIKORNBANK", "short": "KBANK"},
            "account": {
                "name": {"th": "นาย ศุภวิชญ์ ก"},
                "bank": {"type": "BANKAC", "account": "xxx-x-x3341-x"},
            },
        },
        "receiver": {
            "bank": {"id": "014", "name": "SCB", "short": "SCB"},
            "account": {
                "name": {"th": "นาย ศุภวิชญ์ กนกพงศกร"},
                "bank": {"type": "BANKAC", "account": "xxx-x-x7644-x"},
            },
        },
    },
}


def test_easyslip_basic_fields():
    t = parse_easyslip(DATA, OWNER, FB)
    assert t is not None
    assert t.bank == "KBANK"
    assert t.direction == "debit"
    assert t.amount == 1.00
    assert t.account_masked == "3341"
    assert t.counterparty_bank == "SCB"
    assert t.counterparty_account == "7644"


def test_easyslip_uses_real_timestamp():
    t = parse_easyslip(DATA, OWNER, FB)
    # 2026-07-25 19:25 +07:00 -> 12:25 UTC
    assert t.ts == datetime(2026, 7, 25, 12, 25, tzinfo=timezone.utc)


def test_easyslip_internal_detection():
    t = parse_easyslip(DATA, OWNER, FB)
    assert t.is_internal is True


def test_easyslip_not_internal_to_third_party():
    import copy

    d = copy.deepcopy(DATA)
    d["rawSlip"]["receiver"]["account"]["name"]["th"] = "นาย สมชาย ใจดี"
    t = parse_easyslip(d, OWNER, FB)
    assert t.is_internal is False


def test_easyslip_no_amount_returns_none():
    assert parse_easyslip({"rawSlip": {}}, OWNER, FB) is None
