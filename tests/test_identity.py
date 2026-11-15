"""Tests for api_python.identity — locale-aware autofill billing identity."""
from __future__ import annotations

import importlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_python.identity import (  # noqa: E402
    BillingIdentity,
    env_billing_identity,
    generate_billing_identity,
    supported_countries,
)

SUPPORTED = ["BR", "ID", "IN", "NL", "PH", "TH", "VN"]


def test_supported_countries_exact():
    assert supported_countries() == SUPPORTED


def test_all_countries_generate_valid_identity():
    for cc in SUPPORTED:
        ident = generate_billing_identity(cc)
        assert isinstance(ident, BillingIdentity)
        assert ident.country == cc
        # name: two non-empty parts
        parts = ident.name.split()
        assert len(parts) >= 2 and all(p for p in parts)
        # line1: "123 Street Name"
        assert ident.line1.split()[0].isdigit()
        # postal: non-empty digits (NL is 4 digits, others 5-6)
        assert ident.postal.isdigit() and 4 <= len(ident.postal) <= 6
        # phone: starts with +<country digits>-
        assert ident.phone.startswith("+") and "-" in ident.phone


def test_deterministic_with_seed():
    a = generate_billing_identity("IN", seed="job-1")
    b = generate_billing_identity("IN", seed="job-1")
    c = generate_billing_identity("IN", seed="job-2")
    assert a == b
    assert a != c


def test_seed_varies_by_country():
    a = generate_billing_identity("IN", seed="same")
    b = generate_billing_identity("NL", seed="same")
    assert a != b


def test_unsupported_country_raises():
    try:
        generate_billing_identity("XX")
    except ValueError as exc:
        assert "unsupported country" in str(exc)
    else:
        raise AssertionError("expected ValueError for unsupported country")


def test_env_override_wins_over_autofill():
    os.environ["TEST_BILLING_NAME"] = "Custom Name"
    os.environ["TEST_BILLING_CITY"] = "Custom City"
    try:
        ident = env_billing_identity("IN", env_prefix="TEST_BILLING_")
        assert ident.name == "Custom Name"
        assert ident.city == "Custom City"
        # unset fields fall back to autofill (state must be a real IN state)
        assert ident.state in ("MH", "KA", "DL", "TN", "WB")
    finally:
        del os.environ["TEST_BILLING_NAME"]
        del os.environ["TEST_BILLING_CITY"]


def test_env_unset_uses_autofill():
    for key in list(os.environ):
        if key.startswith("TEST2_BILLING_"):
            del os.environ[key]
    ident = env_billing_identity("BR", env_prefix="TEST2_BILLING_")
    assert ident.country == "BR"
    assert ident.name and ident.line1 and ident.city and ident.state and ident.postal


def test_postal_formats_match_country_scheme():
    # spot-check real postal formats
    assert len(generate_billing_identity("NL").postal) == 4          # Dutch 4-digit
    assert generate_billing_identity("IN").postal.startswith(("1", "4", "5", "6", "7"))  # IN pin ranges
    assert len(generate_billing_identity("TH").postal) == 5          # Thai 5-digit


def test_as_dict_roundtrip():
    ident = generate_billing_identity("VN", seed="rt")
    d = ident.as_dict()
    assert d["country"] == "VN"
    assert BillingIdentity(**d) == ident


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    raise SystemExit(1 if failures else 0)
