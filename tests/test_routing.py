"""Tests for source-based routing in process._parse_event.

These paths don't touch the database (sb is unused for notifications), so we
pass sb=None. The gallery path calls into Storage and fails gracefully here,
which is enough to confirm it's routed as a slip.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.process import _parse_event

FB = datetime(2026, 7, 24, 5, 0, tzinfo=timezone.utc)


def test_route_kplus_notification():
    payload = {
        "title": "รายการเงินเข้า",
        "text": "บัญชี xxx-x-x3341-x  จำนวนเงิน 2.00 บาท  วันที่ 23 ก.ค. 69  23:49 น.",
    }
    txn, err, is_slip = _parse_event(None, "kplus", payload, FB)
    assert txn is not None and txn.bank == "KBANK"
    assert txn.direction == "credit" and txn.amount == 2.00
    assert is_slip is False


def test_route_line_app_scb():
    payload = {
        "app": "SCB",
        "title": "SCB Connect",
        "text": "รายการเงินเข้า 1.00 บาท เข้าบัญชี X-6442 วันที่ 23/07/2026 @23:44",
    }
    txn, err, is_slip = _parse_event(None, "line", payload, FB)
    assert txn is not None and txn.bank == "SCB" and is_slip is False


def test_route_uob_source():
    payload = {"text": "มีการใช้บัตร UOB-8340 @TMN 7-11 1.00 THB วันที่ 23"}
    txn, err, is_slip = _parse_event(None, "uob", payload, FB)
    assert txn is not None and txn.bank == "UOB"


def test_route_unknown_source():
    txn, err, is_slip = _parse_event(None, "whatever", {}, FB)
    assert txn is None and "not handled" in err


def test_route_gallery_is_detected_as_slip():
    # Routed as slip; download fails with sb=None but is_slip must be True.
    txn, err, is_slip = _parse_event(None, "gallery-kplus", {"path": "x.jpg"}, FB)
    assert is_slip is True
    assert txn is None and "slip download failed" in err
