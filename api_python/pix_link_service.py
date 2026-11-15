"""Pix rail — BR/BRL payment link extraction via the shared engine.

Reuses the parameterized extraction engine with the Pix spec: BR checkout,
BRL currency, 'pix' payment method type, BR billing identities.

Requires a BR egress proxy (PIX_LINK_PROXY, PAYRAIL_PROXY_PIX, or a
region-rewritable shared proxy).
"""
from __future__ import annotations

from typing import Any

from .rail_specs import PIX_SPEC
from . import upi_link_service as engine


def resolve_pix_proxy() -> str:
    return engine.resolve_rail_proxy("pix")


def extract_pix_link(access_token: str, proxy: str | None = None, *, job_id: str = "", on_step: Any = None) -> dict[str, Any]:
    """Extract a Pix payment link synchronously (CLI / library use)."""
    proxy_url = str(proxy or resolve_pix_proxy() or "").strip()
    if not proxy_url:
        raise RuntimeError("proxy is required for pix extraction (PIX_LINK_PROXY or a region-rewritable base proxy)")
    return engine.extract_upi_link(access_token, proxy_url, job_id=job_id, on_step=on_step, spec=PIX_SPEC)


class PixRail:
    """RailService implementation for the Pix rail."""

    rail_id = "pix"

    def start_extract(self, access_token: str, **kwargs: Any) -> dict[str, Any]:
        return engine.start_rail_extract(self.rail_id, access_token, **kwargs)

    def get_status(self, job_id: str) -> dict[str, Any]:
        return engine.get_upi_link_status(job_id)

    def recover_stale(self, max_age_sec: int | None = None) -> int:
        return engine.recover_stale_upi_records(max_age_sec=max_age_sec)
