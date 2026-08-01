"""UOB credit-card monthly-statement parser (PDF text).

One statement PDF covers ALL of the user's UOB cards for one billing month.
Layout (verified against real statements, `pdfplumber.extract_text`):

  Page 1 — ACCOUNT SUMMARY:
    / STATEMENT DATE 15 JUL 2026
    / PAYMENT DUE DATE 07 AUG 2026
    CARD NUMBER (S)        TOTAL BALANCE  MINIMUM PAYMENT  ...
    5257 20XX XXXX 9762      6,829.20       3,812.00
    ...
    TOTAL                   13,460.87       4,344.00

  Pages 2+ — per-card transaction sections:
    UOB PREMIER
    5257 20XX XXXX 9762
    PREVIOUS BALANCE 95,681.18
    <POST> <TRANS> <DESCRIPTION> <AMOUNT> [CR]
    ...
    SUB TOTAL 6,829.20
    TOTAL BALANCE - UOB PREMIER 6,829.20

Row shapes:
  charge:       "01 JUL 30 JUN TOPS-RAMA 9 BANGKOK 268.00"
  payment:      "07 JUL 07 JUL PAYMENT THANK YOU - UOBT TMRW APP 95,681.18 CR"
  cashback/refund: "... UOB One Cashback 1% 6.71 CR"
  foreign:      "03 JUL 02 JUL ANTHROPIC* CLAUDE SUB SAN FRANCISCO USD21.40 733.73"
                (foreign amount is glued to the currency code; THB is the LAST number)
  installment:  "15 JUL 15 JUL IT CITY - FORTUNE TOWN 06/10 3,549.00 3,549.00"
                (NN/NN = installment n of m; two THB numbers, the LAST is posted)

Rules:
  - trailing "CR" -> a credit (payment / refund / cashback) that REDUCES the card
    balance; otherwise a debit (charge) that increases it.
  - the THB amount is always the LAST money token on the line.
  - a foreign charge has "<CUR><amount>" (e.g. USD21.40, EUR10.28, CHF260.00)
    inside the description; we keep the original currency+amount AND the THB.
  - dates carry no year; infer from the statement date (a trans month greater
    than the statement month rolled over from the previous year).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from . import base

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Currencies seen on foreign charges (extend as needed).
_CURRENCIES = {
    "USD", "EUR", "CHF", "GBP", "JPY", "CNY", "AUD", "SGD", "HKD", "KRW",
    "CAD", "NZD", "THB", "TWD", "MYR", "VND", "AED", "INR", "SEK", "NOK",
    "DKK", "CZK", "PLN",
}

_MONEY = r"\d{1,3}(?:,\d{3})*\.\d{2}"
_MONEY_RE = re.compile(_MONEY)
# a full card number "5257 20XX XXXX 9762" -> last-4
_CARD_RE = re.compile(r"\b(\d{4})\s+\d{2}XX\s+XXXX\s+(\d{4})\b")
# summary row: "<full card> <total balance> <min payment>"
_SUMMARY_ROW_RE = re.compile(
    r"\d{4}\s+\d{2}XX\s+XXXX\s+(\d{4})\s+(" + _MONEY + r")\s+(" + _MONEY + r")"
)
_STMT_DATE_RE = re.compile(r"STATEMENT DATE\s+(\d{1,2})\s+([A-Z]{3})\s+(\d{4})")
_DUE_DATE_RE = re.compile(r"PAYMENT DUE DATE\s+(\d{1,2})\s+([A-Z]{3})\s+(\d{4})")
# a transaction row begins with POST + TRANS dates: "01 JUL 30 JUN ..."
_ROW_RE = re.compile(
    r"^(\d{1,2})\s+([A-Z]{3})\s+(\d{1,2})\s+([A-Z]{3})\s+(.*)$"
)
_INSTALLMENT_RE = re.compile(r"\b(\d{2})/(\d{2})\b")
# foreign amount glued to a currency code inside the description, e.g. USD21.40
_FOREIGN_RE = re.compile(r"\b([A-Z]{3})\s?(" + _MONEY + r")\b")


@dataclass
class StatementRow:
    card_masked: str
    post_date: date
    trans_date: date
    description: str
    thb_amount: float
    direction: str  # 'debit' (charge) | 'credit' (payment/refund/cashback)
    currency: str = "THB"
    foreign_amount: Optional[float] = None
    installment: Optional[str] = None  # "06/10"
    is_payment: bool = False  # "PAYMENT THANK YOU" bill payment


@dataclass
class CardSection:
    card_masked: str
    card_name: str
    previous_balance: Optional[float] = None
    closing_balance: Optional[float] = None  # per-section TOTAL BALANCE
    summary_balance: Optional[float] = None  # page-1 ACCOUNT SUMMARY balance
    min_payment: Optional[float] = None
    rows: list[StatementRow] = field(default_factory=list)


@dataclass
class UobStatement:
    statement_date: Optional[date] = None
    due_date: Optional[date] = None
    account_number: Optional[str] = None
    cards: list[CardSection] = field(default_factory=list)

    def all_rows(self) -> list[StatementRow]:
        out: list[StatementRow] = []
        for c in self.cards:
            out.extend(c.rows)
        return out


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


def _infer_year(month: int, stmt: Optional[date]) -> int:
    if stmt is None:
        return datetime.now().year
    # A trans/post month later than the statement month rolled over the year end
    # (e.g. a JAN statement listing DEC transactions).
    return stmt.year - 1 if month > stmt.month else stmt.year


def _parse_amounts(rest: str) -> tuple[str, float, str, Optional[float], bool]:
    """From the text after the two dates, return
    (description, thb_amount, currency, foreign_amount, is_credit)."""
    is_credit = False
    body = rest.strip()
    if body.endswith(" CR"):
        is_credit = True
        body = body[:-3].strip()

    monies = list(_MONEY_RE.finditer(body))
    if not monies:
        return body, 0.0, "THB", None, is_credit

    # THB is the last money token; description is everything before it.
    last = monies[-1]
    thb = _to_float(last.group(0))
    description = body[: last.start()].strip()

    currency = "THB"
    foreign_amount: Optional[float] = None
    fm = _FOREIGN_RE.search(description)
    if fm and fm.group(1) in _CURRENCIES and fm.group(1) != "THB":
        currency = fm.group(1)
        foreign_amount = _to_float(fm.group(2))
        # strip the "<CUR><amount>" token out of the visible description
        description = (description[: fm.start()] + description[fm.end():]).strip()

    return description, thb, currency, foreign_amount, is_credit


def parse_uob_statement(text: str) -> UobStatement:
    """Parse the full text of a UOB monthly statement PDF (all pages joined)."""
    stmt = UobStatement()

    m = _STMT_DATE_RE.search(text)
    if m:
        stmt.statement_date = date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)))
    m = _DUE_DATE_RE.search(text)
    if m:
        stmt.due_date = date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)))
    m = re.search(r"ACCOUNT NUMBER\s+([\d-]+)", text)
    if m:
        stmt.account_number = m.group(1)

    # --- page-1 ACCOUNT SUMMARY: card -> (total balance, min payment) --------
    summary: dict[str, tuple[float, float]] = {}
    for sm in _SUMMARY_ROW_RE.finditer(text):
        summary[sm.group(1)] = (_to_float(sm.group(2)), _to_float(sm.group(3)))

    # --- per-card transaction sections --------------------------------------
    card_names = {"UOB PREMIER", "UOB WORLD", "UOB ONE", "UOB PRIVI", "UOB LADY"}
    current: Optional[CardSection] = None
    pending_name: Optional[str] = None
    lines = text.splitlines()

    def close(sec: Optional[CardSection]) -> None:
        # Only real transaction sections carry a PREVIOUS BALANCE line; the
        # PAYMENT FORM / PROMOTION pages repeat the card headers with no rows.
        if sec is not None and (sec.previous_balance is not None or sec.rows):
            stmt.cards.append(sec)

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        up = line.upper()
        # Transaction sections always precede the promotion / payment-form pages;
        # everything after those just repeats card headers, so stop here.
        if "PAYMENT FORM" in up or up.startswith("/ PROMOTION") or up == "PROMOTION":
            break

        if up in card_names:
            pending_name = line
            continue

        cm = _CARD_RE.search(line)
        if cm and (pending_name or "PREVIOUS BALANCE" not in up):
            # Start a new card section when we hit its card-number line. Only the
            # section header lines are bare card numbers; guard with pending_name.
            if pending_name is not None:
                close(current)
                last4 = cm.group(2)
                current = CardSection(card_masked=last4, card_name=pending_name)
                if last4 in summary:
                    current.summary_balance, current.min_payment = summary[last4]
                pending_name = None
                continue

        if current is None:
            continue

        if up.startswith("PREVIOUS BALANCE"):
            mv = _MONEY_RE.search(line)
            if mv:
                current.previous_balance = _to_float(mv.group(0))
            continue
        if up.startswith("TOTAL BALANCE -") or up.startswith("SUB TOTAL"):
            mv = _MONEY_RE.search(line)
            if mv and current.closing_balance is None:
                current.closing_balance = _to_float(mv.group(0))
            continue
        if up.startswith("TOTAL FEE") or up.startswith("TOTAL VAT"):
            continue

        rm = _ROW_RE.match(line)
        if not rm:
            continue
        post_m, post_mon = int(rm.group(1)), rm.group(2)
        trans_m, trans_mon = int(rm.group(3)), rm.group(4)
        if post_mon not in _MONTHS or trans_mon not in _MONTHS:
            continue
        rest = rm.group(5)

        desc, thb, currency, foreign_amt, is_credit = _parse_amounts(rest)
        if thb == 0.0 and not desc:
            continue

        post_date = date(_infer_year(_MONTHS[post_mon], stmt.statement_date),
                         _MONTHS[post_mon], post_m)
        trans_date = date(_infer_year(_MONTHS[trans_mon], stmt.statement_date),
                          _MONTHS[trans_mon], trans_m)

        inst = None
        im = _INSTALLMENT_RE.search(desc)
        if im:
            inst = f"{im.group(1)}/{im.group(2)}"

        is_payment = "PAYMENT THANK YOU" in desc.upper()

        current.rows.append(StatementRow(
            card_masked=current.card_masked,
            post_date=post_date,
            trans_date=trans_date,
            description=desc.strip(" .:-"),
            thb_amount=thb,
            direction="credit" if is_credit else "debit",
            currency=currency,
            foreign_amount=foreign_amt,
            installment=inst,
            is_payment=is_payment,
        ))

    close(current)
    return stmt


def extract_text(pdf_bytes: bytes) -> str:
    """Extract all text from a UOB statement PDF (pages joined by newline)."""
    import io

    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)
