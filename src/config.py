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
# treated as the same real-world transfer (e.g. LINE alert + OneDrive slip).
DEDUP_WINDOW_MINUTES = int(os.environ.get("DEDUP_WINDOW_MINUTES", "10"))


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
