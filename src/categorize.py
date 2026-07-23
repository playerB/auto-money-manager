"""Lightweight auto-categorization from counterparty_rules.

This is the seed of the Phase 4 categorization engine: when a transaction's
counterparty matches a saved rule, attach its category. Unknown counterparties
are left uncategorized for the dashboard to resolve (and, once you categorize
one there, a new rule is saved so it's remembered next time).
"""
from __future__ import annotations

import re
from typing import Any, Optional


def load_rules(sb: Client) -> list[dict[str, Any]]:
    resp = (
        sb.table("counterparty_rules")
        .select("*")
        .order("priority", desc=False)
        .execute()
    )
    return resp.data or []


def match_category(
    counterparty: Optional[str], rules: list[dict[str, Any]]
) -> tuple[Optional[int], Optional[int]]:
    """Return (category_id, subcategory_id) for the first matching rule."""
    if not counterparty:
        return None, None
    name = counterparty.strip()
    low = name.lower()
    for rule in rules:
        pattern = str(rule.get("pattern", ""))
        mtype = rule.get("match_type", "contains")
        hit = False
        if mtype == "exact":
            hit = low == pattern.lower()
        elif mtype == "contains":
            hit = pattern.lower() in low
        elif mtype == "regex":
            try:
                hit = re.search(pattern, name, re.IGNORECASE) is not None
            except re.error:
                hit = False
        if hit:
            return rule.get("category_id"), rule.get("subcategory_id")
    return None, None
