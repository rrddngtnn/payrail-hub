"""iDEAL rail — NL/EUR payment link extraction via the shared engine.

Reuses the UPI extraction engine (parameterized by RailSpec) with the
iDEAL spec: NL checkout, EUR currency, 'ideal' payment method type, NL
billing identities from identity.py.

Differences from the UPI rail:
  - No cross-region promo handoff by default (iDEAL trial availability is
    promo-dependent; the rail extracts a full-price link unless a promo
    campaign is configured).
  - Requires an NL egress proxy (IDEAL_LINK_PROXY).
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from .identity import env_billing_identity
from .rail_specs import IDEAL_SPEC
from . import upi_link_service as engine

_NL_PROXY_ENV = "IDEAL_LINK_PROXY"


def resolve_ideal_proxy() -> str:
    import os
    engine._load_env_file()
    direct = str(os.environ.get(_NL_PROXY_ENV, "")).strip()
    if direct:
        return direct
    # Fall back to the shared UPI proxy line with the region rewritten to NL
    base = engine.resolve_upi_proxy()
    return engine.proxy_for_region(base, "NL") if base else ""


def extract_ideal_link(access_token: str, proxy: str | None = None, *, job_id: str = "", on_step: Any = None) -> dict[str, Any]:
    """Extract an iDEAL payment link. Same contract as extract_upi_link."""
    proxy_url = str(proxy or resolve_ideal_proxy() or "").strip()
    if not proxy_url:
        raise RuntimeError("proxy is required for iDEAL extraction (IDEAL_LINK_PROXY or a region-rewritable base proxy)")
    return engine.extract_upi_link(access_token, proxy_url, job_id=job_id, on_step=on_step, spec=IDEAL_SPEC)


class IdealRail:
    """RailService implementation for the iDEAL rail."""

    rail_id = "ideal"

    def start_extract(self, access_token: str, **kwargs: Any) -> dict[str, Any]:
        result = extract_ideal_link(access_token, **kwargs)
        result.setdefault("rail_id", self.rail_id)
        return result

    def get_status(self, job_id: str) -> dict[str, Any]:
        # Jobs share the engine's queue/persistence; status lookup is unified.
        return engine.get_upi_link_status(job_id)

    def recover_stale(self, max_age_sec: int | None = None) -> int:
        return engine.recover_stale_upi_records(max_age_sec=max_age_sec)
