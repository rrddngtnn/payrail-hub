"""Configuration resolution for PayRail Hub.

Reads PAYRAIL_* environment variables, falling back to legacy CHATUPI_*
names for existing deployments. A helper `_cfg()` centralizes resolution
so rail services and admin tooling share one precedence rule:

    explicit PAYRAIL_<NAME>  >  legacy CHATUPI_<NAME>  >  default
"""
from __future__ import annotations

import os


def _cfg(name: str, default: str = "") -> str:
    """Resolve PAYRAIL_<NAME>, then legacy CHATUPI_<NAME>, then default."""
    val = os.environ.get(f"PAYRAIL_{name}", "").strip()
    if val:
        return val
    val = os.environ.get(f"CHATUPI_{name}", "").strip()
    return val or default


def cfg_int(name: str, default: int) -> int:
    raw = _cfg(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def cfg_bool(name: str, default: bool = False) -> bool:
    raw = _cfg(name).lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


# --- Resolved settings (read at import; see main.py for app wiring) ---

def app_root() -> str:
    """Project root for run-output cleanup; defaults to repo root."""
    return os.environ.get("VERIFY_APP_ROOT") or os.environ.get("APP_ROOT") or ""


def database_path(root) -> str:
    """SQLite path; PAYRAIL_DATABASE > CHATUPI_DATABASE > <root>/data/chatupi.sqlite3."""
    return _cfg("DATABASE") or str(root / "data" / "chatupi.sqlite3")


def base_path() -> str:
    return (_cfg("BASE_PATH") or "/CHATUPI").rstrip("/")


def secret_key() -> str:
    return _cfg("SECRET_KEY")


def password_hash() -> str:
    return _cfg("PASSWORD_HASH")


def retention_days() -> int:
    return cfg_int("RETENTION_DAYS", 30)


def hourly_limit() -> int:
    return cfg_int("HOURLY_LIMIT", 10)


def allowed_hosts() -> str:
    return _cfg("ALLOWED_HOSTS") or "localhost,127.0.0.1"


def allow_http() -> bool:
    return cfg_bool("ALLOW_HTTP", False)
