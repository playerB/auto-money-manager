"""Configuration loaded from environment variables.

Locally, values come from a .env file (see .env.example). In GitHub Actions
they come from repository secrets. Never commit real keys.
"""
from __future__ import annotations

import os

try:
    # Optional: load .env when running locally. In CI the vars are already set.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
# Service-role key: used ONLY by the backend processor (never in the phone/app).
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Timezone for interpreting bank timestamps that have no zone info.
LOCAL_TZ = os.environ.get("LOCAL_TZ", "Asia/Bangkok")

# Fuzzy-dedup window: two same-amount transactions within this many minutes are
# treated as the same real-world transfer (e.g. LINE alert + slip).
DEDUP_WINDOW_MINUTES = int(os.environ.get("DEDUP_WINDOW_MINUTES", "10"))

# Supabase Storage bucket where the phone uploads transfer-slip images.
# `or` (not a default arg) so an env var set to "" in CI falls back, not blanks.
SLIP_BUCKET = os.environ.get("SLIP_BUCKET") or "slips"

# Slip reading provider: "easyslip" (QR-verification API) or "ocr" (Tesseract).
# EasySlip returns exact structured data; OCR is the free/local fallback.
SLIP_PROVIDER = os.environ.get("SLIP_PROVIDER", "ocr").strip().lower()
EASYSLIP_API_KEY = os.environ.get("EASYSLIP_API_KEY", "")

# Supabase Storage bucket where statement PDFs are uploaded (via the dashboard).
# `or` so an unset repo secret (which CI injects as "") falls back to the default
# bucket name instead of an empty string (which 404s as "Bucket not found").
STATEMENT_BUCKET = os.environ.get("STATEMENT_BUCKET") or "statements"

# Statement PDF passwords (Thai e-statements are often encrypted). KBANK and UOB
# may differ; leave blank if a bank's PDFs open freely.
KBANK_STATEMENT_PASSWORD = os.environ.get("KBANK_STATEMENT_PASSWORD", "")
UOB_STATEMENT_PASSWORD = os.environ.get("UOB_STATEMENT_PASSWORD", "")


def statement_password(bank: str) -> str:
    """Return the configured PDF password for a bank's statements ('' if none)."""
    return {
        "KBANK": KBANK_STATEMENT_PASSWORD,
        "UOB": UOB_STATEMENT_PASSWORD,
    }.get((bank or "").upper(), "")

# Account-owner FULL names (comma-separated), Thai and/or English, as printed on
# slips. Used to detect internal transfers: a slip is internal only when BOTH
# sender and recipient match the owner. Give the fullest form you have — the
# matcher tolerates redaction/abbreviation (ก / ก. / ก*** / KANO). Example:
#   OWNER_NAMES="นาย ศุภวิชญ์ กนกพงศกร,SUPAWISH KANOKPONGSAKORN"
OWNER_NAMES = [
    k.strip() for k in os.environ.get("OWNER_NAMES", "").split(",") if k.strip()
]

# Window (minutes) for matching a slip's recipient credit to mark it internal.
INTERNAL_MATCH_WINDOW_MINUTES = int(
    os.environ.get("INTERNAL_MATCH_WINDOW_MINUTES", "180")
)


def require_supabase() -> None:
    """Raise a clear error if Supabase credentials are missing."""
    missing = [
        name
        for name, val in (
            ("SUPABASE_URL", SUPABASE_URL),
            ("SUPABASE_SERVICE_KEY", SUPABASE_SERVICE_KEY),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env (local) or set repo secrets (CI)."
        )
