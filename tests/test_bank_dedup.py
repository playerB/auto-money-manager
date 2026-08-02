"""Window-aware bank reconciliation: a PDF statement must recognize live rows
captured from KBANK app notifications even when the two mask different windows
of the same account (alert ...3341 vs statement header ...3416, both inside the
full 0578033416). Regression for duplicate statement rows."""
from __future__ import annotations

from datetime import datetime, timezone

from src.db import account_window_match, load_bank_transactions


def test_window_match_same_account_different_window():
    # Alert stored 3341; statement account is 3416 / full 0578033416.
    assert account_window_match("3341", "3416", "0578033416") is True
    assert account_window_match("3416", "3416", "0578033416") is True


def test_window_match_missing_account_is_permissive():
    # An alert that failed to parse an account still dedups on amount+time.
    assert account_window_match("", "3416", "0578033416") is True
    assert account_window_match(None, "3416", "0578033416") is True


def test_window_match_rejects_unrelated_account():
    assert account_window_match("9999", "3416", "0578033416") is False
    assert account_window_match("1234", "3416", "0578033416") is False


# --- load_bank_transactions integration with a fake Supabase client ---------

class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def execute(self):
        return type("R", (), {"data": self._rows})()


class _FakeSB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _FakeQuery(self._rows)


def test_load_bank_transactions_matches_alert_in_other_window():
    lo = datetime(2026, 6, 1, tzinfo=timezone.utc)
    hi = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = [
        # KBANK app alert stored the ...3341 masking window of the same account.
        {"id": 1, "method": "bank", "bank": "KBANK", "account_masked": "3341",
         "amount": 8000.0, "direction": "debit", "source": "kplus"},
        # An unrelated KBANK account, must NOT be pulled in.
        {"id": 2, "method": "bank", "bank": "KBANK", "account_masked": "9999",
         "amount": 8000.0, "direction": "debit", "source": "kplus"},
        # A prior statement import must never reconcile against itself.
        {"id": 3, "method": "bank", "bank": "KBANK", "account_masked": "3416",
         "amount": 8000.0, "direction": "debit", "source": "statement-kbank"},
    ]
    sb = _FakeSB(rows)
    got = load_bank_transactions(sb, "KBANK", "3416", lo, hi, account_digits="0578033416")
    ids = {r["id"] for r in got}
    assert ids == {1}


# --- canonical account normalization (3341 window -> 3416 real last-4) -------

from src.owner import canonical_account_masked

_ACCTS = [
    {"bank_name": "KBANK", "masked_number": "3416", "full_number": "0578033416", "is_own": True},
    {"bank_name": "SCB", "masked_number": "6442", "full_number": "0384676442", "is_own": True},
]


def test_canonical_maps_window_to_real_last4():
    # KBANK alert reveals the ...3341 window -> normalize to canonical 3416.
    assert canonical_account_masked("KBANK", "3341", _ACCTS) == "3416"
    assert canonical_account_masked("KBANK", "3416", _ACCTS) == "3416"


def test_canonical_is_bank_scoped():
    # 3341 sits inside the KBANK full number, but for an SCB txn it must not map.
    assert canonical_account_masked("SCB", "3341", _ACCTS) is None


def test_canonical_none_for_unknown_account():
    assert canonical_account_masked("KBANK", "9999", _ACCTS) is None
    assert canonical_account_masked("KBANK", "", _ACCTS) is None
