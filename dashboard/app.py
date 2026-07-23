"""Streamlit dashboard (Phase 5 grows this out further).

Run locally:   streamlit run dashboard/app.py
Deploy free:   Streamlit Community Cloud, main file dashboard/app.py.

Security model:
  - This app reads with the Supabase SERVICE key. On Streamlit Community Cloud,
    secrets live server-side and are never sent to the browser, so the key is
    not exposed. A password gate protects the UI itself (apps are public by URL).
  - With RLS enabled on the data tables (migration 002), the public anon key
    used by the phone cannot read your transactions — only insert raw_events.
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Auto Money Manager", page_icon="💸", layout="wide")


def _get(name: str, default: str = "") -> str:
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
    # Service key: server-side only on Community Cloud. Falls back to anon key
    # for local dev if that's all that's set.
    key = _get("SUPABASE_SERVICE_KEY") or _get("SUPABASE_ANON_KEY")
    return create_client(_get("SUPABASE_URL"), key)


@st.cache_data(ttl=60)
def load_transactions() -> pd.DataFrame:
    sb = get_client()
    resp = sb.table("transactions").select("*").order("ts", desc=True).limit(2000).execute()
    df = pd.DataFrame(resp.data or [])
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert("Asia/Bangkok")
    return df


def main() -> None:
    st.title("💸 Auto Money Manager")
    if not check_password():
        st.stop()

    if st.button("↻ Refresh"):
        st.cache_data.clear()

    df = load_transactions()
    if df.empty:
        st.info("No transactions yet. Make a test transfer and run the processor.")
        return

    # Spending totals exclude internal transfers / card payments.
    ext = df[~df.get("is_internal", False).fillna(False)]
    spend = ext.loc[ext["direction"] == "debit", "amount"].sum()
    income = ext.loc[ext["direction"] == "credit", "amount"].sum()
    review = int(df.get("needs_review", pd.Series(dtype="boolean")).fillna(False).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Spending (out)", f"฿{spend:,.2f}")
    c2.metric("Income (in)", f"฿{income:,.2f}")
    c3.metric("Transactions", len(df))
    c4.metric("Needs review", review)

    # Filters
    banks = sorted(df["bank"].dropna().unique().tolist())
    pick = st.multiselect("Bank", banks, default=banks)
    view = df[df["bank"].isin(pick)] if pick else df

    st.subheader("Transactions")
    cols = [
        c
        for c in [
            "ts", "bank", "direction", "amount", "method",
            "counterparty_name", "account_masked", "source",
            "is_internal", "needs_review", "notes",
        ]
        if c in view.columns
    ]
    st.dataframe(
        view[cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "ts": st.column_config.DatetimeColumn("When", format="YYYY-MM-DD HH:mm"),
            "amount": st.column_config.NumberColumn("Amount", format="฿%.2f"),
        },
    )


if __name__ == "__main__":
    main()
