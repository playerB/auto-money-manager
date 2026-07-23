"""Owner-name matching for internal-transfer detection.

Why this is fiddly:
  - The account owner's name appears in many forms on slips: first name only,
    first + surname initial, redacted (`ก`, `ก.`, `ก***`), full Thai, or English
    (`SUPAWISH KANO`, `SUPAWISH KANOKPONGSAKORN`).
  - On own->own transfers the SENDER (you) is usually redacted to just the
    surname initial, while the recipient may be fuller.
  - A friend shares a similar first name, so first-name-only matching is unsafe.

Design:
  - Configure OWNER_NAMES with full names (Thai and/or English). Each yields an
    identity (first name, surname).
  - A slip party matches an identity when the first name matches AND the slip's
    surname is prefix-consistent with the owner's surname (either direction),
    which absorbs redaction/abbreviation ("ก" ~ "กนกพงศกร", "KANO" ~
    "KANOKPONGSAKORN"). The match is "strong" when >=2 surname chars align.
  - Internal transfer requires BOTH sender and recipient to match the owner.
    If both matches are weak (surname fully redacted on both sides), we still
    mark it internal but flag it for review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_TITLES = [
    "นางสาว", "นาย", "นาง", "น.ส.", "ด.ช.", "ด.ญ.",
    "mr", "mrs", "ms", "miss",
]


def normalize(name: str) -> str:
    """Strip title, redaction marks, and punctuation; collapse spaces."""
    s = (name or "").strip()
    s = s.replace("*", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()
    low = s.lower()
    for t in _TITLES:
        if low.startswith(t):
            s = s[len(t):].strip()
            break
    return re.sub(r"\s+", " ", s).strip()


def _tokens(name: str) -> tuple[str, str]:
    """Return (first, surname-without-spaces), upper-cased for comparison."""
    parts = normalize(name).split()
    if not parts:
        return "", ""
    first = parts[0].upper()
    surname = "".join(parts[1:]).upper()
    return first, surname


@dataclass(frozen=True)
class Identity:
    first: str
    surname: str


class OwnerMatcher:
    def __init__(self, owner_names: list[str]):
        self.identities: list[Identity] = []
        for full in owner_names or []:
            f, s = _tokens(full)
            if f:
                self.identities.append(Identity(f, s))

    def match(self, name: str | None) -> tuple[bool, bool]:
        """Return (is_owner, is_strong)."""
        if not name:
            return False, False
        f, sur = _tokens(name)
        if not f:
            return False, False
        for ident in self.identities:
            if f != ident.first:
                continue
            osur = ident.surname
            if not osur:
                # Owner configured without a surname (discouraged): first-name
                # match only. Treat as weak to avoid friend false-positives.
                return True, False
            if not sur:
                # Slip shows first name only -> weak match.
                return True, False
            if sur.startswith(osur) or osur.startswith(sur):
                strong = min(len(sur), len(osur)) >= 2
                return True, strong
            # first name matched but surname inconsistent -> not this identity
        return False, False


def classify_transfer(
    matcher: OwnerMatcher, sender: str | None, recipient: str | None
) -> tuple[bool, bool]:
    """Return (is_internal, is_confident).

    Internal requires BOTH parties to match the owner. Confident when at least
    one side has a strong (non-redacted) surname match.
    """
    s_owner, s_strong = matcher.match(sender)
    r_owner, r_strong = matcher.match(recipient)
    if s_owner and r_owner:
        return True, (s_strong or r_strong)
    return False, False
