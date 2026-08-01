"""UOB monthly-statement parser + reconciliation tests.

Uses an inline statement text in the exact real layout (no personal PDFs are
committed). Reconciliation math is the acceptance test: for each card,
previous_balance + debits − credits must equal the stated closing balance.
"""
from __future__ import annotations

from datetime import date

from src.parsers.statement_uob import parse_uob_statement
from src.statements import _enrich_fields, _find_live_match, _row_to_txn

STMT = """/ ACCOUNT NUMBER 810-03103753396
/ STATEMENT DATE 15 JUL 2026
/ TOTAL CREDIT LINE 248,000
/ PAYMENT DUE DATE 07 AUG 2026
/ ACCOUNT SUMMARY1
CARD NUMBER (S) TOTAL BALANCE MINIMUM PAYMENT DIRECT DEBIT ACCOUNT NO. / BANK
5432 15XX XXXX 8340 4,999.73 301.00
5432 15XX XXXX 1640 168.00 75.00
TOTAL 5,167.73 376.00
POST DATE TRANS DATE DESCRIPTION AMOUNT (THB)
UOB WORLD
5432 15XX XXXX 8340
PREVIOUS BALANCE 1,000.00
07 JUL 07 JUL PAYMENT THANK YOU - UOBT TMRW APP 1,000.00 CR
01 JUL 30 JUN TOPS-RAMA 9 BANGKOK 268.00
03 JUL 02 JUL ANTHROPIC* CLAUDE SUB SAN FRANCISCO USD21.40 733.73
06 JUL 04 JUL NETFLIX.COM Singapore 419.00
06 JUL 03 JUL TMN 7-11 BANGKOK 15.00
06 JUL 03 JUL TMN 7-11 BANGKOK 15.00
15 JUL 15 JUL IT CITY - FORTUNE TOWN 06/10 3,549.00 3,549.00
SUB TOTAL 4,999.73
TOTAL BALANCE - UOB WORLD 4,999.73
TOTAL FEE - UOB WORLD 0.00
TOTAL VAT - UOB WORLD 0.00
UOB ONE
5432 15XX XXXX 1640
PREVIOUS BALANCE 100.00
07 JUL 07 JUL PAYMENT THANK YOU - UOBT TMRW APP 100.00 CR
13 JUL 11 JUL BANGKOK EXPRESSWAY AND BANGKOK 14.00 CR
10 JUL 09 JUL WWW.GRAB.COM BANGKOK 134.00
15 JUL 15 JUL UOB One Cashback 1% 6.71 CR
15 JUL 14 JUL MRT-BEM Bangkok 54.71
SUB TOTAL 168.00
TOTAL BALANCE - UOB ONE 168.00
TOTAL FEE - UOB ONE 0.00
TOTAL VAT - UOB ONE 0.00
/ PROMOTION
UOB WORLD
5432 15XX XXXX 8340
/ PAYMENT FORM
"""


def _parsed():
    return parse_uob_statement(STMT)


# --- statement metadata + structure -----------------------------------------

def test_header_fields():
    st = _parsed()
    assert st.statement_date == date(2026, 7, 15)
    assert st.due_date == date(2026, 8, 7)
    assert st.account_number == "810-03103753396"


def test_only_real_card_sections_kept():
    # The PROMOTION / PAYMENT FORM repeat of card headers must not add sections.
    st = _parsed()
    assert [c.card_masked for c in st.cards] == ["8340", "1640"]


def test_summary_balances_attached():
    st = _parsed()
    by = {c.card_masked: c for c in st.cards}
    assert by["8340"].summary_balance == 4999.73
    assert by["8340"].min_payment == 301.00
    assert by["1640"].summary_balance == 168.00


# --- the acceptance test: balances reconcile --------------------------------

def test_each_card_reconciles():
    st = _parsed()
    for c in st.cards:
        deb = sum(r.thb_amount for r in c.rows if r.direction == "debit")
        cre = sum(r.thb_amount for r in c.rows if r.direction == "credit")
        calc = (c.previous_balance or 0) + deb - cre
        assert abs(calc - c.closing_balance) < 0.005, c.card_masked
        assert abs(c.closing_balance - c.summary_balance) < 0.005, c.card_masked


# --- row-level parsing ------------------------------------------------------

def test_foreign_charge_keeps_currency_and_thb():
    st = _parsed()
    fx = [r for r in st.all_rows() if r.currency != "THB"]
    assert len(fx) == 1
    r = fx[0]
    assert r.currency == "USD"
    assert r.foreign_amount == 21.40
    assert r.thb_amount == 733.73
    assert "USD" not in r.description  # currency token stripped from description
    assert "ANTHROPIC" in r.description


def test_installment_takes_last_amount():
    st = _parsed()
    ins = [r for r in st.all_rows() if r.installment]
    assert len(ins) == 1
    assert ins[0].installment == "06/10"
    assert ins[0].thb_amount == 3549.00
    assert ins[0].direction == "debit"


def test_payment_row_is_credit_and_flagged():
    st = _parsed()
    pays = [r for r in st.all_rows() if r.is_payment]
    assert len(pays) == 2  # one per card
    assert all(p.direction == "credit" for p in pays)


def test_cr_suffix_is_credit():
    st = _parsed()
    # BANGKOK EXPRESSWAY refund + cashback are credits; MRT is a debit.
    one = [c for c in st.cards if c.card_masked == "1640"][0]
    refunds = [r for r in one.rows if r.direction == "credit" and not r.is_payment]
    assert any(abs(r.thb_amount - 14.00) < 0.005 for r in refunds)
    assert any(abs(r.thb_amount - 6.71) < 0.005 for r in refunds)


def test_identical_same_day_rows_both_kept():
    st = _parsed()
    world = [c for c in st.cards if c.card_masked == "8340"][0]
    fifteens = [r for r in world.rows if abs(r.thb_amount - 15.00) < 0.005]
    assert len(fifteens) == 2  # two distinct 15.00 charges same day


def test_year_inference_across_month_boundary():
    st = _parsed()
    world = [c for c in st.cards if c.card_masked == "8340"][0]
    tops = [r for r in world.rows if "TOPS" in r.description][0]
    assert tops.trans_date == date(2026, 6, 30)  # 30 JUN under a JUL statement


# --- ParsedTxn conversion ---------------------------------------------------

def test_row_to_txn_foreign():
    st = _parsed()
    r = [x for x in st.all_rows() if x.currency == "USD"][0]
    txn = _row_to_txn(r, "UOB")
    assert txn.method == "credit_card"
    assert txn.currency == "USD"
    assert txn.amount == 21.40
    assert txn.thb_amount == 733.73
    assert txn.account_masked == "8340"


# --- reconciliation against live rows ---------------------------------------

def test_find_live_match_by_thb():
    st = _parsed()
    netflix = [r for r in st.all_rows() if "NETFLIX" in r.description][0]
    live = [{
        "id": 1, "account_masked": "8340", "direction": "debit",
        "amount": 419.00, "currency": "THB", "thb_amount": None,
        "ts": "2026-07-04T10:00:00+00:00",
    }]
    m = _find_live_match(live, set(), netflix)
    assert m is not None and m["id"] == 1


def test_find_live_match_foreign_by_foreign_amount():
    st = _parsed()
    fx = [r for r in st.all_rows() if r.currency == "USD"][0]
    # A live alert stored the foreign amount (21.40), no THB yet.
    live = [{
        "id": 7, "account_masked": "8340", "direction": "debit",
        "amount": 21.40, "currency": "USD", "thb_amount": None,
        "needs_review": True,  # foreign alerts are flagged until THB is known
        "ts": "2026-07-02T09:00:00+00:00",
    }]
    m = _find_live_match(live, set(), fx)
    assert m is not None and m["id"] == 7
    fields = _enrich_fields(m, fx)
    assert fields["thb_amount"] == 733.73
    assert fields["needs_review"] is False


def test_no_match_outside_window():
    st = _parsed()
    netflix = [r for r in st.all_rows() if "NETFLIX" in r.description][0]
    live = [{
        "id": 1, "account_masked": "8340", "direction": "debit",
        "amount": 419.00, "currency": "THB", "thb_amount": None,
        "ts": "2026-06-01T10:00:00+00:00",  # far from 04 JUL
    }]
    assert _find_live_match(live, set(), netflix) is None


def test_consumed_row_not_rematched():
    st = _parsed()
    netflix = [r for r in st.all_rows() if "NETFLIX" in r.description][0]
    live = [{
        "id": 1, "account_masked": "8340", "direction": "debit",
        "amount": 419.00, "currency": "THB", "thb_amount": None,
        "ts": "2026-07-04T10:00:00+00:00",
    }]
    assert _find_live_match(live, {1}, netflix) is None
