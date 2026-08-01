"""KBANK savings-statement parser + reconciliation tests.

Inline statement text in the exact real layout (no personal PDF committed). The
acceptance test is the running balance: direction and amount are derived from the
printed outstanding balance, and the parsed debit/deposit totals must match the
stated totals.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from src.owner import OwnerMatcher
from src.parsers.statement_kbank import parse_kbank_statement
from src.statements import _find_live_bank_match, _kbank_row_to_txn

OWNER = ["นาย ศุภวิชญ์ กนกพงศกร", "SUPAWISH KANOKPONGSAKORN"]

# Own SCB account (full number contains 6442); everything else is external.
ACCOUNTS = [
    {"type": "bank", "bank_name": "SCB", "masked_number": "6442",
     "full_number": "0384676442", "is_own": True},
    {"type": "bank", "bank_name": "KBANK", "masked_number": "3416",
     "full_number": "0578033416", "is_own": True},
]

STMT = """PAGE/OF 1/3
Account Number 057-8-03341-6
Period 01/06/2026 - 30/07/2026
Owner Branch Thanon Asok Din Daeng Branch
Ending Balance 496,061.38
Total Withdrawal 5 Items 60,462.71
Total Deposit 3 Items 56,524.09
Time/ Outstanding Balance
Date Descriptions Withdrawal / Deposit Channel Details
Eff.Date (THB)
01-06-26 Beginning Balance 500,000.00
07-06-26 13:16 Payment 8,000.00 492,000.00 K PLUS Paid for Ref X0074 YouTrip Powered by
KBank
16-06-26 20:19 Transfer Withdrawal 16,000.00 476,000.00 K PLUS To BAY X5161 JURARAT YON++
20-06-26 16:39 Transfer Withdrawal 5,388.00 470,612.00 K PLUS To KTB X6807 MR. SUPAWISH KANOK++
21-06-26 21:59 Transfer Deposit 435.00 471,047.00 Other Bank From SCB X6348 นาย ภูมิภากร สาระน++
23-07-26 23:44 Transfer Withdrawal 1.00 471,046.00 K PLUS To SCB X6442 SUPAWISH KA++
23-07-26 23:49 Transfer Deposit 2.00 471,048.00 Internet/Mobile SCB From SCB X6442 นาย ศุภวิชญ์ กนกพง++
29-06-26 02:11 Automatic Deposit 56,087.09 527,135.09 Automatic Transfer From SMART CITI X7007 Agoda Services Co
.++
30-07-26 15:09 Transfer Withdrawal 31,073.71 496,061.38 K PLUS To UOBT X5291 MR.SUPAWISH KANOKP++
Issued by K PLUS
"""


def _parsed():
    return parse_kbank_statement(STMT)


def test_header_fields():
    st = _parsed()
    assert st.account_number == "057-8-03341-6"
    assert st.account_digits == "0578033416"
    assert st.account_masked == "3416"
    assert st.period_start == date(2026, 6, 1)
    assert st.period_end == date(2026, 7, 30)
    assert st.beginning_balance == 500000.00
    assert st.ending_balance == 496061.38


def test_direction_from_balance_delta():
    st = _parsed()
    by_amt = {r.amount: r for r in st.rows}
    assert by_amt[8000.00].direction == "debit"
    assert by_amt[435.00].direction == "credit"
    assert by_amt[56087.09].direction == "credit"
    assert all(r.balance_ok for r in st.rows)


def test_totals_reconcile():
    st = _parsed()
    deb = [r for r in st.rows if r.direction == "debit"]
    cre = [r for r in st.rows if r.direction == "credit"]
    assert len(deb) == 5 and abs(sum(r.amount for r in deb) - 60462.71) < 0.005
    assert len(cre) == 3 and abs(sum(r.amount for r in cre) - 56524.09) < 0.005
    run = st.beginning_balance + sum(r.amount for r in cre) - sum(r.amount for r in deb)
    assert abs(run - st.ending_balance) < 0.005


def test_beginning_balance_not_a_transaction():
    st = _parsed()
    assert all(r.ttype != "Beginning Balance" for r in st.rows)
    assert len(st.rows) == 8


def test_multiline_details_joined():
    st = _parsed()
    youtrip = [r for r in st.rows if "YouTrip" in (r.counterparty_name or "")][0]
    assert "KBank" in youtrip.counterparty_name  # continuation line folded in


def test_transfer_counterparty_parsed():
    st = _parsed()
    bay = [r for r in st.rows if r.amount == 16000.00][0]
    assert bay.counterparty_bank == "BAY"
    assert bay.counterparty_acct == "5161"
    assert bay.counterparty_name == "JURARAT YON"  # trailing ++ stripped


def test_uobt_normalized_to_uob():
    st = _parsed()
    uob = [r for r in st.rows if r.amount == 31073.71][0]
    assert uob.counterparty_bank == "UOB"
    assert uob.counterparty_acct == "5291"


def test_payment_merchant_parsed():
    st = _parsed()
    yt = [r for r in st.rows if r.amount == 8000.00][0]
    assert yt.ref == "X0074"
    assert "YouTrip" in yt.counterparty_name


# --- internal detection via _kbank_row_to_txn -------------------------------

def _txn_for(amount: float):
    st = _parsed()
    row = [r for r in st.rows if r.amount == amount][0]
    return _kbank_row_to_txn(row, st, OwnerMatcher(OWNER), ACCOUNTS)


def test_internal_by_own_account_scb():
    # To SCB X6442 -> own account by number.
    txn = _txn_for(1.00)
    assert txn.is_internal is True
    assert txn.needs_review is False


def test_internal_by_owner_name_ktb():
    # To KTB X6807 MR. SUPAWISH KANOK -> owner by name (not in accounts).
    txn = _txn_for(5388.00)
    assert txn.is_internal is True


def test_external_transfer_not_internal():
    txn = _txn_for(16000.00)  # JURARAT YON
    assert txn.is_internal is False


def test_agoda_deposit_external():
    txn = _txn_for(56087.09)  # Agoda payout -> income, external
    assert txn.is_internal is False
    assert txn.direction == "credit"


def test_payment_never_internal():
    txn = _txn_for(8000.00)  # a Payment, not a transfer
    assert txn.is_internal is False


# --- reconciliation against live rows ---------------------------------------

def test_live_bank_match_by_amount_and_time():
    st = _parsed()
    row = [r for r in st.rows if r.amount == 16000.00][0]
    txn = _kbank_row_to_txn(row, st, OwnerMatcher(OWNER), ACCOUNTS)
    live = [{
        "id": 5, "direction": "debit", "amount": 16000.00,
        "ts": txn.ts.isoformat(),
    }]
    assert _find_live_bank_match(live, set(), "debit", 16000.00, txn.ts)["id"] == 5


def test_live_bank_match_respects_direction():
    when = datetime(2026, 6, 16, 13, 19, tzinfo=timezone.utc)
    live = [{"id": 1, "direction": "credit", "amount": 16000.00, "ts": when.isoformat()}]
    assert _find_live_bank_match(live, set(), "debit", 16000.00, when) is None
