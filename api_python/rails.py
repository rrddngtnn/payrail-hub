"""Rail contract for PayRail Hub extraction services.

Each payment rail (UPI, iDEAL, Pix, GoPay, ...) implements this protocol so
the FastAPI layer can register and route to it without rail-specific code.

A rail bundles:
  - public entry points (start/status/proxy resolution/recovery)
  - a queue name and job persistence directory

The UPI rail (upi_link_service.py) predates this contract; it satisfies it
structurally. New rails should subclass `Rail` for shared bookkeeping.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RailService(Protocol):
    """Structural contract implemented by every payment rail service."""

    #: short rail identifier, e.g. "upi", "ideal", "pix"
    rail_id: str

    def start_extract(self, access_token: str, **kwargs: Any) -> dict[str, Any]:
        """Queue or start an extraction job. Returns {'job_id', 'queue_status', ...}."""
        ...

    def get_status(self, job_id: str) -> dict[str, Any]:
        """Return job status: {'status', 'steps', 'long_url', 'error', ...}."""
        ...

    def recover_stale(self, max_age_sec: int | None = None) -> int:
        """Requeue/fail jobs whose worker died. Returns recovered count."""
        ...


def upi_service_adapter():
    """Adapt the existing UPI service module to the RailService protocol."""
    from . import upi_link_service as svc

    class _UpiRail:
        rail_id = "upi"

        def start_extract(self, access_token: str, **kwargs: Any) -> dict[str, Any]:
            return svc.start_upi_link_extract(access_token, **kwargs)

        def get_status(self, job_id: str) -> dict[str, Any]:
            return svc.get_upi_link_status(job_id)

        def recover_stale(self, max_age_sec: int | None = None) -> int:
            return svc.recover_stale_upi_records(max_age_sec=max_age_sec)

    return _UpiRail()


RAILS: dict[str, RailService] = {}


def register_rail(service: RailService) -> None:
    if not isinstance(service, RailService):
        raise TypeError(f"{service!r} does not satisfy the RailService protocol")
    RAILS[service.rail_id] = service


def get_rail(rail_id: str) -> RailService:
    try:
        return RAILS[rail_id]
    except KeyError:
        raise KeyError(
            f"unknown rail {rail_id!r}; registered: {sorted(RAILS) or 'none'}"
        ) from None


def bootstrap_default_rails() -> None:
    """Register the built-in rails once (idempotent)."""
    if "upi" not in RAILS:
        register_rail(upi_service_adapter())
