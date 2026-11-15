"""Tests for api_python.rails — rail registration and routing contract."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_python import rails  # noqa: E402
from api_python.rails import (  # noqa: E402
    RAILS,
    RailService,
    bootstrap_default_rails,
    get_rail,
    register_rail,
)


class FakeRail:
    rail_id = "fake"

    def start_extract(self, access_token: str, **kwargs) -> dict:
        return {"job_id": "j1", "queue_status": "started"}

    def get_status(self, job_id: str) -> dict:
        return {"status": "completed", "long_url": "fake://pay?x=1"}

    def recover_stale(self, max_age_sec: int | None = None) -> int:
        return 0


def test_fake_rail_satisfies_protocol():
    assert isinstance(FakeRail(), RailService)


def test_register_and_get():
    register_rail(FakeRail())
    assert get_rail("fake").rail_id == "fake"
    del RAILS["fake"]


def test_unknown_rail_raises_with_registered_list():
    try:
        get_rail("nope")
    except KeyError as exc:
        assert "unknown rail" in str(exc)
    else:
        raise AssertionError("expected KeyError")


def test_non_conforming_object_rejected():
    class NotARail:
        pass

    try:
        register_rail(NotARail())
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")


def test_bootstrap_registers_upi_idempotent():
    bootstrap_default_rails()
    bootstrap_default_rails()  # second call must not duplicate
    assert list(RAILS) == ["upi"]
    svc = get_rail("upi")
    assert isinstance(svc, RailService)
    assert svc.rail_id == "upi"
    del RAILS["upi"]


def test_upi_adapter_routes_to_real_service():
    bootstrap_default_rails()
    svc = get_rail("upi")
    assert hasattr(svc, "start_extract")
    assert hasattr(svc, "get_status")
    assert hasattr(svc, "recover_stale")
    del RAILS["upi"]


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
