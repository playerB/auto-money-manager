"""Bank notification parsers.

Each parser takes the raw LINE notification (title, text) plus a timestamp hint
and returns a ParsedTxn or None if it doesn't recognize the message.

IMPORTANT: the regex patterns in kbank.py / uob.py are best-effort starting
points. Thai bank LINE alert wording varies by product and changes over time.
Paste 2-3 real (redacted) notifications and we tune the patterns to match
exactly. Until then, unmatched fields are flagged needs_review rather than
guessed.
"""
from __future__ import annotations

from .base import ParsedTxn, dispatch

__all__ = ["ParsedTxn", "dispatch"]
