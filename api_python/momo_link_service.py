"""MoMo rail — VN/VND payment link extraction via the shared engine.

Reuses the parameterized extraction engine with the MoMo spec: VN
checkout, VND currency, 'momo' payment method type, VN billing
identities.

Requires a VN egress proxy (MOMO_LINK_PROXY, PAYRAIL_PROXY_MOMO, or a
region-rewritable shared proxy).
"""
from __future__ import annotations

from typing import Any

from .rail_specs import MOMO_SPEC
from . import upi_link_service as engine


def resolve_momo_proxy() -> str:
    return engine.resolve_rail_proxy("momo")


def extract_momo_link(access_token: str, proxy: str | None = None, *, job_id: str = "", on_step: Any = None) -> dict[str, Any]:
    """Extract a MoMo payment link synchronously (CLI / library use)."""
    proxy_url = str(proxy or resolve_momo_proxy() or "").strip()
    if not proxy_url:
        raise RuntimeError("proxy is required for momo extraction (MOMO_LINK_PROXY or a region-rewritable base proxy)")
    return engine.extract_upi_link(access_token, proxy_url, job_id=job_id, on_step=on_step, spec=MOMO_SPEC)


class MomoRail:
    """RailService implementation for the MoMo rail."""

    rail_id = "momo"

    def start_extract(self, access_token: str, **kwargs: Any) -> dict[str, Any]:
        return engine.start_rail_extract(self.rail_id, access_token, **kwargs)

    def get_status(self, job_id: str) -> dict[str, Any]:
        return engine.get_upi_link_status(job_id)

    def recover_stale(self, max_age_sec: int | None = None) -> int:
        return engine.recover_stale_upi_records(max_age_sec=max_age_sec)
