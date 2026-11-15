"""Rail specifications — per-rail parameters for the extraction engine.

The extraction engine (upi_link_service.py and its successors) is region/
method parameterized through these specs. UPI is the reference rail; iDEAL
demonstrates the contract for a second locale (NL / EUR).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RailSpec:
    """Parameterization of one local payment rail."""

    rail_id: str
    #: country for checkout + billing identity (ISO alpha-2)
    country: str
    #: currency code (Stripe minor-unit context)
    currency: str
    #: Stripe payment method type offered by this rail
    payment_method_type: str
    #: browser locale sent to Stripe init form
    browser_locale: str
    #: timezone sent to Stripe init form
    timezone: str
    #: env prefix for billing identity overrides (e.g. UPI_BILLING_NAME)
    billing_env_prefix: str
    #: regexes that recognize an extracted payment URL for this rail
    url_patterns: tuple[str, ...] = ()
    #: accept-language for the checkout country client
    accept_language: str = ""
    #: promo campaign (None → no promo step; rail pays full price)
    promo_campaign_id: str | None = "plus-1-month-free"
    #: promotion region used to apply the promo (None → skip handoff)
    promotion_region: str | None = "VN"

    def checkout_body(self, plan_name: str = "chatgptplusplan") -> dict:
        return {
            "entry_point": "all_plans_pricing_modal",
            "plan_name": plan_name,
            "billing_details": {"country": self.country, "currency": self.currency},
            "checkout_ui_mode": "custom",
            **({"promo_campaign": {"promo_campaign_id": self.promo_campaign_id, "is_coupon_from_query_param": False}}
               if self.promo_campaign_id else {}),
        }

    def matches_payment_url(self, url: str) -> bool:
        u = str(url or "").strip()
        if not u:
            return False
        return any(re.search(pat, u, re.I) for pat in self.url_patterns)


UPI_SPEC = RailSpec(
    rail_id="upi",
    country="IN",
    currency="INR",
    payment_method_type="upi",
    browser_locale="en-IN",
    timezone="Asia/Kolkata",
    billing_env_prefix="UPI_BILLING_",
    url_patterns=(
        r"upi://pay[^\s\"'<>]*",
        r"https://payments\.stripe\.com/upi/instructions/[^\s\"'<>]+",
        r"https://hooks\.stripe\.com/redirect/[^\s\"'<>]+",
    ),
    accept_language="en-IN,en;q=0.9",
)

IDEAL_SPEC = RailSpec(
    rail_id="ideal",
    country="NL",
    currency="EUR",
    payment_method_type="ideal",
    browser_locale="en-NL",
    timezone="Europe/Amsterdam",
    billing_env_prefix="IDEAL_BILLING_",
    url_patterns=(
        r"https://.*\.ideal\.issuing[^\s\"'<>]*",
        r"https://.*\.stripe\.com/.*ideal[^\s\"'<>]*",
        r"https://hooks\.stripe\.com/redirect/[^\s\"'<>]+",
    ),
    accept_language="en-NL,nl;q=0.9",
    # iDEAL trial availability is promo-dependent and historically regional;
    # no cross-region handoff by default — rail extracts a full-price link.
    promo_campaign_id=None,
    promotion_region=None,
)

SPECS: dict[str, RailSpec] = {s.rail_id: s for s in (UPI_SPEC, IDEAL_SPEC)}


def get_spec(rail_id: str) -> RailSpec:
    try:
        return SPECS[rail_id]
    except KeyError:
        raise KeyError(f"unknown rail {rail_id!r}; known: {sorted(SPECS)}") from None
