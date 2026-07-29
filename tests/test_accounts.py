"""Account-number matching for internal-transfer detection.

Covers the real masking problem: different sources reveal different digit
windows of the SAME account (SCB shows ...6442, a KBANK slip shows ...7644 —
both substrings of the full 0384676442), so we substring-match revealed digits
against each own account's stored full_number.
"""
from __future__ import annotations

from src.owner import OwnerMatcher, classify_internal, own_account_match

# Mirrors the real `accounts` table: SCB bank account (full number known), a
# KBANK account, a UOB credit card (last-4 only), and a non-own friend account.
ACCOUNTS = [
    {"type": "bank", "bank_name": "SCB", "masked_number": "6442",
     "full_number": "0384676442", "is_own": True},
    {"type": "bank", "bank_name": "KBANK", "masked_number": "3341",
     "full_number": "1234563341", "is_own": True},
    {"type": "credit_card", "bank_name": "UOB", "masked_number": "8340",
     "full_number": None, "is_own": True},
    {"type": "bank", "bank_name": "KBANK", "masked_number": "9999",
     "full_number": "9999999999", "is_own": False},
]

OWNER = ["นาย ศุภวิชญ์ กนกพงศกร", "SUPAWISH KANOKPONGSAKORN"]


# --- own_account_match ------------------------------------------------------

def test_substring_matches_middle_window():
    # KBANK slip reveals 7644, which sits mid-way through SCB's full number.
    assert own_account_match("SCB", "7644", ACCOUNTS) is True


def test_substring_matches_trailing_window():
    # SCB's own alert reveals the trailing 6442.
    assert own_account_match("SCB", "6442", ACCOUNTS) is True


def test_masked_string_with_separators_is_normalized():
    assert own_account_match("SCB", "xxx-x-x7644-x", ACCOUNTS) is True


def test_unknown_digits_do_not_match():
    assert own_account_match("SCB", "5555", ACCOUNTS) is False


def test_bank_scoping_rejects_cross_bank_coincidence():
    # 6442 is SCB's; asking under KBANK must NOT match SCB's full number.
    assert own_account_match("KBANK", "6442", ACCOUNTS) is False


def test_unknown_bank_is_not_scoped():
    # Slips often omit the sender bank; an empty bank should still match.
    assert own_account_match("", "7644", ACCOUNTS) is True


def test_card_last4_matches_via_masked_number():
    assert own_account_match("UOB", "8340", ACCOUNTS) is True


def test_non_own_account_is_ignored():
    assert own_account_match("KBANK", "9999", ACCOUNTS) is False


def test_empty_inputs():
    assert own_account_match("SCB", "", ACCOUNTS) is False
    assert own_account_match("SCB", "6442", []) is False


# --- classify_internal ------------------------------------------------------

def test_own_to_own_by_account_is_internal_and_confident():
    is_internal, confident = classify_internal(
        OwnerMatcher(OWNER),
        ACCOUNTS,
        sender_name=None, sender_bank="KBANK", sender_acct="3341",
        recipient_name=None, recipient_bank="SCB", recipient_acct="7644",
    )
    assert is_internal is True
    assert confident is True


def test_own_to_friend_is_not_internal():
    is_internal, confident = classify_internal(
        OwnerMatcher(OWNER),
        ACCOUNTS,
        sender_name="ศุภวิชญ์ ก", sender_bank="KBANK", sender_acct="3341",
        recipient_name="สมชาย ใจดี", recipient_bank="KBANK", recipient_acct="9999",
    )
    assert is_internal is False
    assert confident is False


def test_name_fallback_when_account_unknown():
    # No usable account digits on either side -> fall back to owner names.
    is_internal, confident = classify_internal(
        OwnerMatcher(OWNER),
        ACCOUNTS,
        sender_name="SUPAWISH KANOKPONGSAKORN", sender_bank=None, sender_acct=None,
        recipient_name="SUPAWISH KANO", recipient_bank=None, recipient_acct=None,
    )
    assert is_internal is True
    assert confident is True  # both surnames align strongly


def test_account_anchors_confidence_despite_redacted_name():
    # Sender name fully redacted, but its account is own -> still confident on
    # that side; recipient anchored by account too.
    is_internal, confident = classify_internal(
        OwnerMatcher(OWNER),
        ACCOUNTS,
        sender_name="นาย ก", sender_bank="KBANK", sender_acct="3341",
        recipient_name=None, recipient_bank="SCB", recipient_acct="6442",
    )
    assert is_internal is True
    assert confident is True


def test_one_side_own_other_unknown_is_not_internal():
    is_internal, confident = classify_internal(
        OwnerMatcher(OWNER),
        ACCOUNTS,
        sender_name=None, sender_bank="SCB", sender_acct="6442",
        recipient_name="Someone Else", recipient_bank="BBL", recipient_acct="1111",
    )
    assert is_internal is False
    assert confident is False
