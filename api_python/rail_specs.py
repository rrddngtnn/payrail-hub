"""Rail specifications — per-rail parameters for the extraction engine.

The extraction engine (upi_link_service.py) is region/method parameterized
through these specs. UPI is the reference rail; iDEAL/Pix/GoPay/MoMo
demonstrate the contract for additional locales.

URL patterns are matched case-insensitively against extracted payment
redirects. Stripe generic redirects are included as a fallback because
every rail resolves through the same hosted-redirect flow.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass


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
    #: promo campaign (None = no promo step; rail extracts a full-price link)
    promo_campaign_id: str | None = "plus-1-month-free"
    #: promotion region used to apply the promo (None = skip handoff)
    promotion_region: str | None = "VN"
    #: display label for UI/API discovery
    label: str = ""
    #: primary env var holding this rail's egress proxy
    proxy_env_var: str = ""
    #: max allowed Stripe minor-unit amount (None = no ceiling enforced)
    amount_policy_max: int | None = None

    def display_label(self) -> str:
        return self.label or self.rail_id.upper()

    def resolve_promo_campaign(self) -> str | None:
        env_val = os.environ.get(f"PAYRAIL_PROMO_{self.rail_id.upper()}", "").strip()
        if env_val.lower() in ("none", "off", "0", "false"):
            return None
        return env_val or self.promo_campaign_id

    def resolve_promotion_region(self) -> str | None:
        env_val = os.environ.get(f"PAYRAIL_PROMO_REGION_{self.rail_id.upper()}", "").strip()
        if env_val.lower() in ("none", "off", "0", "false"):
            return None
        if env_val:
            return env_val.upper()
        return self.promotion_region if self.resolve_promo_campaign() else None

    def resolve_amount_max(self) -> int | None:
        for key in (f"PAYRAIL_AMOUNT_MAX_{self.rail_id.upper()}", "PAYRAIL_AMOUNT_MAX"):
            raw = os.environ.get(key, "").strip()
            if raw:
                if raw.lower() in ("none", "off", "unlimited", "0"):
                    return None
                try:
                    return int(raw)
                except ValueError:
                    pass
        return self.amount_policy_max

    def checkout_body(self, plan_name: str | None = None) -> dict:
        plan = (plan_name or os.environ.get("PAYRAIL_PLAN_NAME", "")).strip() or "chatgptplusplan"
        promo = self.resolve_promo_campaign()
        return {
            "entry_point": "all_plans_pricing_modal",
            "plan_name": plan,
            "billing_details": {"country": self.country, "currency": self.currency},
            "checkout_ui_mode": "custom",
            **({"promo_campaign": {"promo_campaign_id": promo, "is_coupon_from_query_param": False}}
               if promo else {}),
        }

    def matches_payment_url(self, url: str) -> bool:
        u = str(url or "").strip()
        if not u:
            return False
        return any(re.search(pat, u, re.I) for pat in self.url_patterns)


_UPI_PATTERNS = (
    r"upi://pay[^\s\"<>]*",
    r"https://payments\.stripe\.com/upi/instructions/[^\s\"<>]+",
    r"https://hooks\.stripe\.com/redirect/[^\s\"<>]+",
)

_IDEAL_PATTERNS = (
    r"https://[^\s\"<>]*\.ideal[^\s\"<>]*",
    r"https://[^\s\"<>]*\.stripe\.com/[^\s\"<>]*ideal[^\s\"<>]*",
    r"https://hooks\.stripe\.com/redirect/[^\s\"<>]+",
)

_PIX_PATTERNS = (
    r"https://[^\s\"<>]*\.bcb\.gov\.br[^\s\"<>]*",
    r"https://[^\s\"<>]*\.stripe\.com/[^\s\"<>]*pix[^\s\"<>]*",
    r"https://hooks\.stripe\.com/redirect/[^\s\"<>]+",
)

_GOPAY_PATTERNS = (
    r"https://[^\s\"<>]*(?:gopay|midtrans|gojek)[^\s\"<>]*",
    r"https://[^\s\"<>]*\.stripe\.com/[^\s\"<>]*(?:gopay|qr)[^\s\"<>]*",
    r"https://hooks\.stripe\.com/redirect/[^\s\"<>]+",
)

_MOMO_PATTERNS = (
    r"https://[^\s\"<>]*\.momo[^\s\"<>]*",
    r"https://[^\s\"<>]*\.stripe\.com/[^\s\"<>]*momo[^\s\"<>]*",
    r"https://hooks\.stripe\.com/redirect/[^\s\"<>]+",
)


UPI_SPEC = RailSpec(
    rail_id="upi",
    label="UPI (India)",
    country="IN",
    currency="INR",
    payment_method_type="upi",
    browser_locale="en-IN",
    timezone="Asia/Kolkata",
    billing_env_prefix="UPI_BILLING_",
    proxy_env_var="UPI_LINK_PROXY",
    amount_policy_max=50000,
    url_patterns=_UPI_PATTERNS,
    accept_language="en-IN,en;q=0.9,hi;q=0.8",
)

IDEAL_SPEC = RailSpec(
    rail_id="ideal",
    label="iDEAL (Netherlands)",
    country="NL",
    currency="EUR",
    payment_method_type="ideal",
    browser_locale="en-NL",
    timezone="Europe/Amsterdam",
    billing_env_prefix="IDEAL_BILLING_",
    proxy_env_var="IDEAL_LINK_PROXY",
    url_patterns=_IDEAL_PATTERNS,
    accept_language="en-NL,nl;q=0.9",
    promo_campaign_id=None,
    promotion_region=None,
)

PIX_SPEC = RailSpec(
    rail_id="pix",
    label="Pix (Brazil)",
    country="BR",
    currency="BRL",
    payment_method_type="pix",
    browser_locale="pt-BR",
    timezone="America/Sao_Paulo",
    billing_env_prefix="PIX_BILLING_",
    proxy_env_var="PIX_LINK_PROXY",
    url_patterns=_PIX_PATTERNS,
    accept_language="pt-BR,pt;q=0.9,en;q=0.8",
    promo_campaign_id=None,
    promotion_region=None,
)

GOPAY_SPEC = RailSpec(
    rail_id="gopay",
    label="GoPay (Indonesia)",
    country="ID",
    currency="IDR",
    payment_method_type="gopay",
    browser_locale="en-ID",
    timezone="Asia/Jakarta",
    billing_env_prefix="GOPAY_BILLING_",
    proxy_env_var="GOPAY_LINK_PROXY",
    url_patterns=_GOPAY_PATTERNS,
    accept_language="en-ID,id;q=0.9",
    promo_campaign_id=None,
    promotion_region=None,
)

MOMO_SPEC = RailSpec(
    rail_id="momo",
    label="MoMo (Vietnam)",
    country="VN",
    currency="VND",
    payment_method_type="momo",
    browser_locale="vi-VN",
    timezone="Asia/Ho_Chi_Minh",
    billing_env_prefix="MOMO_BILLING_",
    proxy_env_var="MOMO_LINK_PROXY",
    url_patterns=_MOMO_PATTERNS,
    accept_language="vi-VN,vi;q=0.9,en;q=0.8",
    promo_campaign_id=None,
    promotion_region=None,
)

SPECS: dict[str, RailSpec] = {
    s.rail_id: s
    for s in (UPI_SPEC, IDEAL_SPEC, PIX_SPEC, GOPAY_SPEC, MOMO_SPEC)
}


def get_spec(rail_id: str) -> RailSpec:
    rid = str(rail_id or "").strip().lower()
    try:
        return SPECS[rid]
    except KeyError:
        raise KeyError(f"unknown rail {rail_id!r}; known: {sorted(SPECS)}") from None
