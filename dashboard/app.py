"""Minimal Streamlit dashboard stub (Phase 5 grows this out).

Run locally:   streamlit run dashboard/app.py
Deploy free:   Streamlit Community Cloud, pointed at this repo.

Auth: this stub includes a simple password gate. Streamlit Community Cloud apps
are public by default, so set APP_PASSWORD as a secret before deploying.
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Auto Money Manager", page_icon="💸", layout="wide")


def _get(name: str, default: str = "") -> str:
    # Streamlit secrets first, then environment.
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


def check_password() -> bool:
    expected = _get("APP_PASSWORD")
    if not expected:
        st.warning("APP_PASSWORD is not set — dashboard is unprotected.")
        return True
    if st.session_state.get("authed"):
        return True
    pw = st.text_input("Password", type="password")
    if pw and pw == expected:
        st.session_state["authed"] = True
        return True
    if pw:
        st.error("Incorrect password.")
    return False


@st.cache_resource
def get_client():
    return create_client(_get("SUPABASE_URL"), _get("SUPABASE_ANON_KEY"))


def load_transactions(sb) -> pd.DataFrame:
    resp = (
        sb.table("transactions")
        .select("*")
        .order("ts", desc=True)
        .limit(1000)
        .execute()
    )
    df = pd.DataFrame(resp.data or [])
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"])
    return df


def main() -> None:
    st.title("💸 Auto Money Manager")
    if not check_password():
        st.stop()

    sb = get_client()
    df = load_transactions(sb)

    if df.empty:
        st.info("No transactions yet. Send a test bank notification from your phone.")
        return

    debit = df.loc[df["direction"] == "debit", "amount"].sum()
    credit = df.loc[df["direction"] == "credit", "amount"].sum()
    review = int(df.get("needs_review", pd.Series(dtype=bool)).sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Total out", f"฿{debit:,.2f}")
    c2.metric("Total in", f"฿{credit:,.2f}")
    c3.metric("Needs review", review)

    st.subheader("Recent transactions")
    st.dataframe(
        df[
            [
                "ts",
                "direction",
                "amount",
                "method",
                "counterparty_name",
                "source",
                "needs_review",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    main()
