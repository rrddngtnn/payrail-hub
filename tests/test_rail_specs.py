"""Tests for rail specs — checkout body generation, URL matchers, registry."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_python.rail_specs import (  # noqa: E402
    IDEAL_SPEC,
    MOMO_SPEC,
    PIX_SPEC,
    GOPAY_SPEC,
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


def test_new_rails_checkout_bodies():
    for spec, cc, cur in ((PIX_SPEC, "BR", "BRL"), (GOPAY_SPEC, "ID", "IDR"), (MOMO_SPEC, "VN", "VND")):
        body = spec.checkout_body()
        assert body["billing_details"] == {"country": cc, "currency": cur}
        assert "promo_campaign" not in body
        assert spec.promotion_region is None


def test_new_rails_url_matchers():
    assert PIX_SPEC.matches_payment_url("https://www.bcb.gov.br/pix/qr/123")
    assert GOPAY_SPEC.matches_payment_url("https://api.midtrans.com/v2/gopay/charge")
    assert MOMO_SPEC.matches_payment_url("https://test-payment.momo.vn/v2/gateway/pay")
    # cross-rail isolation
    assert not PIX_SPEC.matches_payment_url("upi://pay?pa=x")
    assert not MOMO_SPEC.matches_payment_url("https://www.bcb.gov.br/pix/qr/1")


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
    assert get_spec("pix") is PIX_SPEC
    assert get_spec("gopay") is GOPAY_SPEC
    assert get_spec("momo") is MOMO_SPEC
    try:
        get_spec("nope")
    except KeyError as exc:
        assert "unknown rail" in str(exc)
    else:
        raise AssertionError("expected KeyError")


def test_registry_has_all_rails():
    bootstrap_default_rails()
    assert sorted(RAILS) == ["gopay", "ideal", "momo", "pix", "upi"]
    assert get_rail("pix").rail_id == "pix"
    assert get_rail("gopay").rail_id == "gopay"
    assert get_rail("momo").rail_id == "momo"
    RAILS.clear()


def test_rails_require_proxy():
    # With no proxy configured anywhere, every rail must fail fast with a clear error
    for var in ("IDEAL_LINK_PROXY", "PIX_LINK_PROXY", "GOPAY_LINK_PROXY", "MOMO_LINK_PROXY", "UPI_LINK_PROXY"):
        os.environ.pop(var, None)
    bootstrap_default_rails()
    for rail_id in ("ideal", "pix", "gopay", "momo"):
        try:
            get_rail(rail_id).start_extract("dummy-token")
        except RuntimeError as exc:
            assert "proxy is required" in str(exc), f"{rail_id}: {exc}"
        else:
            raise AssertionError(f"{rail_id}: expected RuntimeError for missing proxy")
    RAILS.clear()


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
