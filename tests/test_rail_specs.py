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
    import tempfile
    # With no proxy configured anywhere, every rail must fail fast with a clear error
    with tempfile.TemporaryDirectory() as empty_root:
        prev_root = os.environ.get("VERIFY_APP_ROOT")
        os.environ["VERIFY_APP_ROOT"] = empty_root
        for var in (
            "IDEAL_LINK_PROXY", "PIX_LINK_PROXY", "GOPAY_LINK_PROXY", "MOMO_LINK_PROXY", "UPI_LINK_PROXY",
            "PAYRAIL_PROXY", "PAYRAIL_PROXY_IDEAL", "PAYRAIL_PROXY_PIX", "PAYRAIL_PROXY_GOPAY",
            "PAYRAIL_PROXY_MOMO", "PAYRAIL_PROXY_UPI", "OPENAI_PAY_DEFAULT_PROXY",
        ):
            os.environ.pop(var, None)
        try:
            bootstrap_default_rails()
            for rail_id in ("upi", "ideal", "pix", "gopay", "momo"):
                res = get_rail(rail_id).start_extract("dummy-token")
                assert res.get("success") is False, f"{rail_id}: {res}"
                assert "proxy is required" in res.get("error", ""), f"{rail_id}: {res}"

            from api_python.ideal_link_service import extract_ideal_link
            from api_python.pix_link_service import extract_pix_link
            from api_python.gopay_link_service import extract_gopay_link
            from api_python.momo_link_service import extract_momo_link
            for fn in (extract_ideal_link, extract_pix_link, extract_gopay_link, extract_momo_link):
                try:
                    fn("dummy-token")
                except RuntimeError as exc:
                    assert "proxy is required" in str(exc)
                else:
                    raise AssertionError(f"{fn.__name__}: expected RuntimeError for missing proxy")
        finally:
            if prev_root is None:
                os.environ.pop("VERIFY_APP_ROOT", None)
            else:
                os.environ["VERIFY_APP_ROOT"] = prev_root
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
