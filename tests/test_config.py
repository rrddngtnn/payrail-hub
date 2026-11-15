"""Tests for api_python.config — PAYRAIL_* environment resolution."""
from __future__ import annotations

import importlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_python import config  # noqa: E402

CANON = "PAYRAIL_"


def _clear(name: str):
    os.environ.pop(f"{CANON}{name}", None)
    os.environ.pop("CHATUPI_" + name, None)  # defensive: legacy name must never resolve


def _reload():
    return importlib.reload(config)


def test_default_when_both_unset():
    _clear("BASE_PATH")
    cfg = _reload()
    assert cfg.base_path() == "/payrail"
    assert cfg.retention_days() == 30
    assert cfg.hourly_limit() == 10
    assert cfg.allowed_hosts() == "localhost,127.0.0.1"
    assert cfg.allow_http() is False
    assert cfg.secret_key() == ""


def test_legacy_chatupi_names_ignored():
    _clear("BASE_PATH")
    os.environ["CHATUPI_BASE_PATH"] = "/LEGACY"
    cfg = _reload()
    assert cfg.base_path() == "/payrail"  # legacy name has no effect


def test_int_parsing_and_bad_values():
    _clear("HOURLY_LIMIT")
    os.environ[f"{CANON}HOURLY_LIMIT"] = "77"
    assert _reload().hourly_limit() == 77
    os.environ[f"{CANON}HOURLY_LIMIT"] = "not-a-number"
    assert _reload().hourly_limit() == 10  # falls back to default
    _clear("HOURLY_LIMIT")


def test_bool_parsing():
    _clear("ALLOW_HTTP")
    for raw, expected in [("1", True), ("true", True), ("yes", True), ("on", True),
                          ("0", False), ("false", False), ("no", False), ("off", False),
                          ("garbage", False)]:
        os.environ[f"{CANON}ALLOW_HTTP"] = raw
        assert _reload().allow_http() is expected, f"ALLOW_HTTP={raw!r}"
    _clear("ALLOW_HTTP")


def test_whitespace_only_values_ignored():
    _clear("SECRET_KEY")
    os.environ[f"{CANON}SECRET_KEY"] = "   "
    os.environ["CHATUPI_SECRET_KEY"] = "legacy-key-value"
    assert _reload().secret_key() == ""  # whitespace ignored, legacy name not consulted
    _clear("SECRET_KEY")


def test_database_path_falls_back_to_repo_layout():
    _clear("DATABASE")
    from pathlib import Path
    root = Path("/tmp/fake-root")
    assert config.database_path(root) == "/tmp/fake-root/data/payrail.sqlite3"
    os.environ[f"{CANON}DATABASE"] = "/custom/db.sqlite3"
    assert config.database_path(root) == "/custom/db.sqlite3"
    _clear("DATABASE")


def test_password_hash_resolution():
    _clear("PASSWORD_HASH")
    os.environ[f"{CANON}PASSWORD_HASH"] = "pbkdf2_sha256$new"
    assert _reload().password_hash() == "pbkdf2_sha256$new"
    _clear("PASSWORD_HASH")


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
