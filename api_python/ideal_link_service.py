"""iDEAL rail — NL/EUR payment link extraction via the shared engine.

Reuses the UPI extraction engine (parameterized by RailSpec) with the
iDEAL spec: NL checkout, EUR currency, 'ideal' payment method type, NL
billing identities from identity.py.

Requires an NL egress proxy (IDEAL_LINK_PROXY, PAYRAIL_PROXY_IDEAL, or
a region-rewritable shared proxy).
"""
from __future__ import annotations

from typing import Any

from .rail_specs import IDEAL_SPEC
from . import upi_link_service as engine


def resolve_ideal_proxy() -> str:
    return engine.resolve_rail_proxy("ideal")


def extract_ideal_link(access_token: str, proxy: str | None = None, *, job_id: str = "", on_step: Any = None) -> dict[str, Any]:
    """Extract an iDEAL payment link synchronously (CLI / library use)."""
    proxy_url = str(proxy or resolve_ideal_proxy() or "").strip()
    if not proxy_url:
        raise RuntimeError("proxy is required for iDEAL extraction (IDEAL_LINK_PROXY or a region-rewritable base proxy)")
    return engine.extract_upi_link(access_token, proxy_url, job_id=job_id, on_step=on_step, spec=IDEAL_SPEC)


class IdealRail:
    """RailService implementation for the iDEAL rail."""

    rail_id = "ideal"

    def start_extract(self, access_token: str, **kwargs: Any) -> dict[str, Any]:
        return engine.start_rail_extract(self.rail_id, access_token, **kwargs)

    def get_status(self, job_id: str) -> dict[str, Any]:
        return engine.get_upi_link_status(job_id)

    def recover_stale(self, max_age_sec: int | None = None) -> int:
        return engine.recover_stale_upi_records(max_age_sec=max_age_sec)
