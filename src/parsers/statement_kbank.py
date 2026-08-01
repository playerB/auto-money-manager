"""KBANK savings-account statement parser (PDF text, K PLUS e-statement).

Layout (verified against a real STM_SA statement via pdfplumber.extract_text):

  Header (repeats each page):
    Account Number 057-8-03341-6           <- full number (contains 3341 AND 3416)
    Period 01/06/2026 - 30/07/2026
    Ending Balance 549,052.82
    Total Withdrawal 64 Items 206,591.25
    Total Deposit    31 Items 145,475.51

  Rows (running-balance ledger):
    DD-MM-YY HH:MM <Type> <Amount> <Outstanding Balance> <Channel> <Details...>
    01-06-26 Beginning Balance 610,168.56          <- balance checkpoint (no txn)
    07-06-26 13:16 Payment 8,000.00 602,168.56 K PLUS Paid for Ref X0074 YouTrip...
    16-06-26 20:19 Transfer Withdrawal 16,000.00 598,028.44 K PLUS To BAY X5161 JURARAT YON++
    21-06-26 21:59 Transfer Deposit 435.00 591,525.88 K PLUS From X1331 MR. Tanyatorn Rojm++

Key facts we exploit:
  - Every row prints the OUTSTANDING BALANCE after it, so direction (debit vs
    credit) and the amount are cross-checked against the balance delta — the
    strongest possible self-verification.
  - The first two money tokens on a row are always Amount then Balance; the
    Details (which may wrap onto following lines) come after and are ignored for
    the numeric parse.
  - Details encode the counterparty: transfers as "To/From [BANK] X<last4>
    <NAME>" (name truncated with ++), payments as "Paid for Ref X<ref> <merchant>".
  - Year is a 2-digit CE year (26 -> 2026), NOT Buddhist era.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

_MONEY = r"\d{1,3}(?:,\d{3})*\.\d{2}"
_MONEY_RE = re.compile(_MONEY)
_DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{2})\b")
_TIME_RE = re.compile(r"^(\d{2}):(\d{2})\b")
_ACCT_RE = re.compile(r"Account Number\s+([\d-]+)")
_PERIOD_RE = re.compile(r"Period\s+(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2})/(\d{2})/(\d{4})")
_ENDING_RE = re.compile(r"Ending Balance\s+(" + _MONEY + r")")
_TOTAL_W_RE = re.compile(r"Total Withdrawal\s+(\d+)\s+Items?\s+(" + _MONEY + r")")
_TOTAL_D_RE = re.compile(r"Total Deposit\s+(\d+)\s+Items?\s+(" + _MONEY + r")")

# counterparty patterns inside the Details text
_TRANSFER_RE = re.compile(
    r"\b(To|From)\s+(?:(PromptPay|SMART CITI|[A-Z]{2,5})\s+)?X(\w+)\s+(.+)$"
)
_PAYMENT_RE = re.compile(r"Paid for Ref\s+(\S+)\s+(.+)$")
_REFCODE_RE = re.compile(r"Ref Code\s+(\S+)")

# Lines that are page furniture, never transaction rows.
_SKIP_PREFIXES = (
    "PAGE/OF", "Ref. No.", "Account", "Period", "Owner Branch", "Ending Balance",
    "Total Withdrawal", "Total Deposit", "Time/", "Date", "Eff.Date", "(THB)",
    "Issued by", "For more information", "FDPBK",
)


@dataclass
class KbankRow:
    date: date
    time: Optional[str]
    ttype: str
    amount: float
    balance: float
    direction: str  # 'debit' | 'credit' (from the balance delta)
    channel: Optional[str] = None
    details: str = ""
    counterparty_name: Optional[str] = None
    counterparty_bank: Optional[str] = None
    counterparty_acct: Optional[str] = None
    ref: Optional[str] = None
    balance_ok: bool = True  # amount == |balance delta|


@dataclass
class KbankStatement:
    account_number: Optional[str] = None
    account_masked: Optional[str] = None       # last 4 (real ending, e.g. 3416)
    account_digits: Optional[str] = None        # all digits (for own-account match)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    beginning_balance: Optional[float] = None
    ending_balance: Optional[float] = None
    total_withdrawal: Optional[float] = None
    total_withdrawal_count: Optional[int] = None
    total_deposit: Optional[float] = None
    total_deposit_count: Optional[int] = None
    rows: list[KbankRow] = field(default_factory=list)


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


# known channel strings, longest first (so multiword ones win)
_CHANNELS = [
    "EDC/K SHOP/MYQR",
    "Internet/Mobile SCB", "Internet/Mobile KK", "Internet/Mobile UOBT",
    "Internet/Mobile BBL", "Internet/Mobile BAY", "Internet/Mobile KTB",
    "Automatic Transfer", "Other Bank", "K PLUS", "CDM", "ATM",
]

# known bank codes seen in transfer details
_BANK_CODES = {"SCB", "BBL", "BAY", "KTB", "KK", "UOBT", "TTB", "GSB", "KKP", "CIMB"}
_BANK_TO_CODE = {"UOBT": "UOB"}  # normalize KBANK's label to our internal code


def _split_channel(after_balance: str) -> tuple[Optional[str], str]:
    for ch in _CHANNELS:
        if after_balance.startswith(ch + " "):
            return ch, after_balance[len(ch):].strip()
        if after_balance == ch:
            return ch, ""
    return None, after_balance


def _parse_counterparty(row: KbankRow) -> None:
    """Fill counterparty_* from the details text, by transaction type."""
    d = row.details.strip()

    tm = _TRANSFER_RE.search(d)
    if tm:
        bank_raw = tm.group(2)
        row.counterparty_acct = tm.group(3)[-4:] if tm.group(3) else None
        name = tm.group(4).strip()
        name = re.sub(r"\+*$", "", name).strip()  # drop trailing ++ truncation
        row.counterparty_name = name or None
        if bank_raw and bank_raw not in ("PromptPay",):
            row.counterparty_bank = _BANK_TO_CODE.get(bank_raw, bank_raw)
        return

    pm = _PAYMENT_RE.search(d)
    if pm:
        row.ref = pm.group(1)
        merchant = pm.group(2).strip()
        row.counterparty_name = merchant or None
        return

    # cash / interest / other
    low = d.lower()
    rc = _REFCODE_RE.search(d)
    if rc:
        row.ref = rc.group(1)
    if row.ttype == "Cash Deposit":
        row.counterparty_name = "Cash deposit"
    elif row.ttype == "Cash Withdrawal":
        row.counterparty_name = "ATM withdrawal"
    elif row.ttype == "Interest Deposit" or "interest" in low:
        row.counterparty_name = "Interest"


def _parse_row_block(
    d: date, time: Optional[str], body: str
) -> Optional[KbankRow]:
    monies = list(_MONEY_RE.finditer(body))
    if len(monies) < 2:
        return None  # need amount + balance
    amount = _to_float(monies[0].group(0))
    balance = _to_float(monies[1].group(0))
    ttype = body[: monies[0].start()].strip()
    after_balance = body[monies[1].end():].strip()
    channel, details = _split_channel(after_balance)

    row = KbankRow(
        date=d, time=time, ttype=ttype, amount=amount, balance=balance,
        direction="debit", channel=channel, details=details,
    )
    _parse_counterparty(row)
    return row


def parse_kbank_statement(text: str) -> KbankStatement:
    st = KbankStatement()

    m = _ACCT_RE.search(text)
    if m:
        st.account_number = m.group(1)
        digits = re.sub(r"\D", "", m.group(1))
        st.account_digits = digits
        st.account_masked = digits[-4:] if len(digits) >= 4 else None
    m = _PERIOD_RE.search(text)
    if m:
        st.period_start = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        st.period_end = date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
    m = _ENDING_RE.search(text)
    if m:
        st.ending_balance = _to_float(m.group(1))
    m = _TOTAL_W_RE.search(text)
    if m:
        st.total_withdrawal_count = int(m.group(1))
        st.total_withdrawal = _to_float(m.group(2))
    m = _TOTAL_D_RE.search(text)
    if m:
        st.total_deposit_count = int(m.group(1))
        st.total_deposit = _to_float(m.group(2))

    # --- walk lines, grouping continuation lines into their row block --------
    # Beginning-Balance rows are balance checkpoints (they repeat at each page
    # break); they carry no transaction. We only record the first as the opening
    # balance — the running balance for direction/verification is driven purely
    # by each row's printed outstanding balance in the second pass.
    blocks: list[tuple[date, Optional[str], list[str]]] = []
    cur: Optional[tuple[date, Optional[str], list[str]]] = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(line.startswith(p) for p in _SKIP_PREFIXES):
            continue

        dm = _DATE_RE.match(line)
        if dm:
            d = date(2000 + int(dm.group(3)), int(dm.group(2)), int(dm.group(1)))
            rest = line[dm.end():].strip()
            tm = _TIME_RE.match(rest)
            time = None
            if tm:
                time = f"{tm.group(1)}:{tm.group(2)}"
                rest = rest[tm.end():].strip()

            if rest.startswith("Beginning Balance"):
                mv = _MONEY_RE.search(rest)
                if mv and st.beginning_balance is None:
                    st.beginning_balance = _to_float(mv.group(0))
                cur = None
                continue

            cur = (d, time, [rest])
            blocks.append(cur)
        else:
            # continuation of the current row's details (skip footer noise)
            if cur is not None and not line.startswith(")") and line not in ("+", "++"):
                cur[2].append(line)
            elif cur is not None and line in ("+", "++"):
                cur[2][-1] = cur[2][-1] + line

    running: Optional[float] = st.beginning_balance
    for d, time, parts in blocks:
        body = " ".join(parts)
        row = _parse_row_block(d, time, body)
        if row is None:
            continue
        # direction + verification from the running balance delta
        if running is not None:
            delta = round(row.balance - running, 2)
            row.direction = "credit" if delta > 0 else "debit"
            row.balance_ok = abs(abs(delta) - row.amount) < 0.005
        running = row.balance
        st.rows.append(row)

    return st
