# PayRail Hub — Local Payment Link Extractors

[![CI](https://github.com/rrddngtnn/payrail-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/rrddngtnn/payrail-hub/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)

Multi-rail toolkit for extracting local payment links (UPI, iDEAL, Pix, GoPay, MoMo, ...) from hosted checkout flows, with locale-aware autofill billing identities.

## Credits

The UPI extraction method was pioneered by [Niceswz/chatgpt-upi-extractor](https://github.com/Niceswz/chatgpt-upi-extractor) — the India checkout → Vietnam promo handoff design originates from that project. Additional protocol research by the [wutianj/upi-link-extractor](https://github.com/wutianj/upi-link-extractor) and [Lyhh0729/ideal-link-extractor](https://github.com/Lyhh0729/ideal-link-extractor) communities.

## Overview

**PayRail Hub** is a FastAPI + SQLite toolkit that generates local payment links for ChatGPT Plus (works with PhonePe / GPay / Paytm and similar payment apps), with a locale-aware autofill billing identity module.

## Features

- 🔐 **Password-protected admin console** (Session Cookie + CSRF) — activate by setting `PAYRAIL_PASSWORD_HASH` in `.env`; leaving it empty is for local debugging only
- 🗄️ **SQLite job queue** (single-concurrency extraction, persistent job records)
- 🌏 **Dual-proxy strategy**: India proxy for checkout/UPI steps, Vietnam proxy for the promo step
- 👤 **Autofill billing identity** (`api_python/identity.py`): generates localized names/addresses/postal codes/phones per country — supports IN / ID / NL / BR / VN / PH / TH, seed-reproducible, any field overridable via env vars
- 🔄 **Online / maintenance mode** toggle (admin-controlled)
- ⚛️ **React components** embeddable into larger portal frontends

## Rails

| Rail | Country | Status |
|---|---|---|
| UPI | 🇮🇳 IN | ✅ Working (core of this repo) |
| iDEAL | 🇳🇱 NL | 🧪 Implemented — shares the extraction engine via `RailSpec`; needs NL egress proxy; promo availability is regional |
| Pix | 🇧🇷 BR | 🧪 Implemented — `PIX_LINK_PROXY`; full-price extraction |
| GoPay | 🇮🇩 ID | 🧪 Implemented — `GOPAY_LINK_PROXY`; full-price extraction |
| MoMo | 🇻🇳 VN | 🧪 Implemented — `MOMO_LINK_PROXY`; full-price extraction |

## Project Layout

```
payrail-hub/
  .env                 # secrets & proxy config (never commit)
  .env.example         # environment variable template
  data/                # SQLite database (gitignored)
  run-output/          # job debug artifacts (gitignored)
  api_python/          # FastAPI application package
    identity.py        # locale-aware autofill billing identity
    rails.py           # rail registration & routing contract
    rail_specs.py      # per-rail parameters (country, currency, method type)
    upi_link_service.py  # UPI rail + shared extraction engine
    ideal_link_service.py  # iDEAL rail (NL/EUR)
    pix_link_service.py    # Pix rail (BR/BRL)
    gopay_link_service.py  # GoPay rail (ID/IDR)
    momo_link_service.py   # MoMo rail (VN/VND)
  scripts/             # CLI tools
  src/components/      # React embed components
  deploy/              # systemd + nginx examples
```

### Adding a new rail

Implement the `RailService` protocol (`api_python/rails.py`) — `start_extract`, `get_status`, `recover_stale` — and call `register_rail()` (see `bootstrap_default_rails()` for the wiring pattern). The FastAPI layer routes through the registry, so no app-code changes are needed per rail.

The service listens on `127.0.0.1:8104` only, exposed externally via Nginx at the `/payrail/` path (configurable).

## Environment Variables

Copy `.env.example` to `.env` (production: `/opt/payrail/.env`) and fill in:

| Variable | Description |
|---|---|
| `PAYRAIL_SECRET_KEY` | Random session cookie key (≥48 chars) |
| `PAYRAIL_PASSWORD_HASH` | PBKDF2 password hash (`pbkdf2_sha256$...` format) — if empty, the admin console runs without auth |
| `PAYRAIL_BASE_PATH` | Public base path, e.g. `/payrail` |
| `PAYRAIL_DATABASE` | SQLite database path (default `data/payrail.sqlite3`, resolved relative to repo root) |
| `PAYRAIL_RETENTION_DAYS` | Job record retention in days (default 30) |
| `PAYRAIL_HOURLY_LIMIT` | Max jobs per user per hour (default 10) |
| `PAYRAIL_ALLOWED_HOSTS` | Allowed hostnames, comma-separated (default `localhost,127.0.0.1`) |
| `VERIFY_APP_ROOT` | Project root for run-output cleanup (default: repo root) |
| `PAYRAIL_PROXY` | Shared region-rewritable proxy URL (`__cr.<cc>`, `cr.<cc>`, `region-<CC>`) |
| `PAYRAIL_PROXY_<RAIL>` / `<RAIL>_LINK_PROXY` | Per-rail egress proxy override (e.g. `UPI_LINK_PROXY`, `IDEAL_LINK_PROXY`, `PIX_LINK_PROXY`, `GOPAY_LINK_PROXY`, `MOMO_LINK_PROXY`) |
| `PAYRAIL_PROMOTION_PROXY` / `UPI_LINK_PROMOTION_PROXY` | Dedicated promo-region exit proxy URL (used by promo handoff rails like UPI) |
| `PAYRAIL_AMOUNT_MAX_<RAIL>` | Optional Stripe minor-unit amount cap (`none` to disable) |
| `PAYRAIL_PLAN_NAME` | Target checkout plan slug (default `chatgptplusplan`) |

Optional proxy-specific file: copy `env_upi_link.txt.example` to `env_upi_link.txt`.

### Billing Identity (optional override)

Each rail generates a locale-appropriate billing identity automatically via `identity.py` (using `<RAIL>_BILLING_*` prefixes: `UPI_BILLING_`, `IDEAL_BILLING_`, `PIX_BILLING_`, `GOPAY_BILLING_`, `MOMO_BILLING_`). To pin specific fields, override any of:

```
<RAIL>_BILLING_NAME=...
<RAIL>_BILLING_LINE1=...
<RAIL>_BILLING_CITY=...
<RAIL>_BILLING_STATE=...
<RAIL>_BILLING_POSTAL=...
```

Any field left unset is autofilled per locale by `identity.py`.

### Identity API

```python
from api_python.identity import generate_billing_identity, env_billing_identity

# Random Indian identity
ident = generate_billing_identity("IN")

# Reproducible via seed (same seed → same identity)
ident = generate_billing_identity("VN", seed="job-123")

# Env override with autofill fallback
ident = env_billing_identity("IN", env_prefix="UPI_BILLING_")
```

Supported countries: IN, ID, NL, BR, VN, PH, TH (postal formats match each country's real scheme).

### Generating the password hash

```bash
python -c "from api_python.security import hash_password; print(hash_password('your-password'))"
```

## Running Locally

```bash
# 1. Ensure the venv module is available
sudo apt update
sudo apt install python3-venv python3-full -y

# 2. Create a virtual environment in the project directory
python3 -m venv venv

# 3. Activate it
source venv/bin/activate   # Linux / macOS
# Windows: venv\Scripts\activate

# 4. Install dependencies and start
pip install -r requirements.txt
export PAYRAIL_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export PAYRAIL_PASSWORD_HASH="$(python -c 'from api_python.security import hash_password; print(hash_password("changeme"))')"
export PAYRAIL_ALLOWED_HOSTS="localhost,127.0.0.1"
python -m uvicorn api_python.main:app --host 127.0.0.1 --port 8104
```

Open `http://127.0.0.1:8104/payrail/login` in a browser (or your configured `PAYRAIL_BASE_PATH`).

> ⚠️ **Use a single Uvicorn worker only**: the extraction queue and live job state live in process memory; multiple workers cause inconsistent state.

## Production Deployment

`deploy/` contains example systemd unit files and Nginx configs — adjust paths, usernames, and hostnames for your environment. **Never commit real secrets, proxy credentials, or production hostnames.**

### Docker

```bash
docker build -t payrail-hub .
docker run --rm -p 127.0.0.1:8104:8104 --env-file .env -v $(pwd)/data:/app/data payrail-hub
```

## Security Notes

- Session JSON / access tokens are used in memory for the current job only, never written to SQLite in plaintext.
- Proxy URLs shown in the console are masked.
- All error messages are sanitized before being returned to clients.
- The QuickJS Sentinel helper passes a sanitized minimal environment to Node.js (secrets and proxy credentials are never forwarded).
- `.env`, database files, and token dumps are all excluded via `.gitignore`.

## Optional Modules

- **`chatgpt_rt_oauth`** / **bundled QuickJS Sentinel (`sentinel_quickjs.py`)**: approval requests look for `chatgpt_rt_oauth` first, then automatically fall back to `sentinel_quickjs.py` when Node.js is installed (disable with `PAYRAIL_QUICKJS_SENTINEL=0`).
- **`src/components/`**: React embed components for host portal projects (accept `defaultRail`, `rails`, and `endpoints` props). Ships with `src/utils/`, `src/constants/`, and stubs so imports resolve standalone. Host projects must install React and `lucide-react` themselves.

## Frontend Dependencies (embed components only)

```text
react
lucide-react
```

This repo does not include a full SPA build; the primary UI is the FastAPI admin console under `api_python/templates/`.

## License

MIT — see [LICENSE](LICENSE).
