"""Tests for proxy masking (credential leak prevention) in CLI and admin surfaces."""
from __future__ import annotations

import importlib.util
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _load_cli_module():
    """Load scripts/run_upi_extract_local.py without running main()."""
    path = os.path.join(os.path.dirname(__file__), "..", "scripts", "run_upi_extract_local.py")
    spec = importlib.util.spec_from_file_location("run_upi_extract_local", path)
    assert spec is not None and spec.loader is not None
    # The CLI imports api_python.* relative to repo root; ensure it's on sys.path
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mask_like_cli(proxy: str) -> str:
    """Calls the actual masking helper from the CLI script."""
    mod = _load_cli_module()
    return mod._mask_proxy_url(proxy)


def test_cli_mask_hides_credentials():
    raw = "http://USER207394-zone-custom-region-IN:secret@global.rotgb.trustsource.live:10000"
    masked = _mask_like_cli(raw)
    assert "secret" not in masked
    assert "USER207394" not in masked
    assert masked == "http://***@global.rotgb.trustsource.live:10000"


def test_cli_mask_handles_schemeless():
    raw = "user:pass@host:1234"
    masked = _mask_like_cli(raw)
    assert "pass" not in masked and "user:" not in masked
    assert masked.endswith("@host:1234")


def test_cli_mask_passthrough_when_no_creds():
    raw = "http://1.2.3.4:8080"
    assert _mask_like_cli(raw) == raw


def test_admin_mask_service():
    from api_python.upi_link_admin_service import _mask_proxy
    masked = _mask_proxy("http://user:secret@host:1")
    assert "secret" not in str(masked)


def test_cli_module_importable():
    mod = _load_cli_module()
    assert hasattr(mod, "main")


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
