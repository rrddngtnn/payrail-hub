"""Tests for rail specs — checkout body generation, URL matchers, registry."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_python.rail_specs import (  # noqa: E402
    IDEAL_SPEC,
    UPI_SPEC,
    SPECS,
    get_spec,
)
from api_python.rails import (  # noqa: E402
    RAILS,
    bootstrap_default_rails,
    get_rail,
)


def test_upi_spec_checkout_body():
    body = UPI_SPEC.checkout_body()
    assert body["billing_details"] == {"country": "IN", "currency": "INR"}
    assert body["promo_campaign"]["promo_campaign_id"] == "plus-1-month-free"
    assert body["checkout_ui_mode"] == "custom"


def test_ideal_spec_checkout_body_no_promo():
    body = IDEAL_SPEC.checkout_body()
    assert body["billing_details"] == {"country": "NL", "currency": "EUR"}
    assert "promo_campaign" not in body  # promo_campaign_id=None → key omitted


def test_url_matchers_per_rail():
    assert UPI_SPEC.matches_payment_url("upi://pay?pa=test&pn=x")
    assert UPI_SPEC.matches_payment_url("https://payments.stripe.com/upi/instructions/abc")
    assert not UPI_SPEC.matches_payment_url("https://example.com/ideal/start")
    assert IDEAL_SPEC.matches_payment_url("https://abn.ideal.issuing.de/pay/123")
    assert IDEAL_SPEC.matches_payment_url("https://hooks.stripe.com/redirect/xyz")
    assert not IDEAL_SPEC.matches_payment_url("upi://pay?pa=x")


def test_get_spec_known_and_unknown():
    assert get_spec("upi") is UPI_SPEC
    assert get_spec("ideal") is IDEAL_SPEC
    try:
        get_spec("nope")
    except KeyError as exc:
        assert "unknown rail" in str(exc)
    else:
        raise AssertionError("expected KeyError")


def test_registry_has_both_rails():
    bootstrap_default_rails()
    assert sorted(RAILS) == ["ideal", "upi"]
    assert get_rail("ideal").rail_id == "ideal"
    assert get_rail("upi").rail_id == "upi"
    RAILS.clear()


def test_ideal_rail_requires_proxy(monkeypatch_env=None):
    # With no proxy configured anywhere, extraction must fail fast with a clear error
    os.environ.pop("IDEAL_LINK_PROXY", None)
    os.environ.pop("UPI_LINK_PROXY", None)
    bootstrap_default_rails()
    rail = get_rail("ideal")
    try:
        rail.start_extract("dummy-token")
    except RuntimeError as exc:
        assert "proxy is required" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for missing proxy")


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
