"""Tests for universal engine flexibility: proxy rewrite/precedence, locales, DB rail_id, API routing."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _clear_proxy_env():
    for k in list(os.environ):
        if k.startswith(("PAYRAIL_PROXY", "UPI_LINK_", "IDEAL_LINK_", "PIX_LINK_", "GOPAY_LINK_", "MOMO_LINK_", "OPENAI_PAY_")):
            os.environ.pop(k, None)


def test_proxy_for_region_dataimpulse_and_generic():
    from api_python.upi_link_service import proxy_for_region

    di = "http://user__cr.in;sessttl.30:pass@gw.example.com:10000"
    assert proxy_for_region(di, "NL") == "http://user__cr.nl;sessttl.30:pass@gw.example.com:10000"
    assert proxy_for_region(di, "BR") == "http://user__cr.br;sessttl.30:pass@gw.example.com:10000"

    di2 = "http://user;cr.in:pass@gw.example.com:10000"
    assert proxy_for_region(di2, "VN") == "http://user;cr.vn:pass@gw.example.com:10000"

    ts = "http://USER-zone-custom-region-IN-st-mh-sid-123:pass@proxy.example.com:10000"
    assert proxy_for_region(ts, "NL") == "http://USER-zone-custom-region-NL-sid-123:pass@proxy.example.com:10000"

    ipr = "http://u:p@geo.iproyal.com:12321_country-region-IN"
    assert "region-br" in proxy_for_region(ipr, "BR")

    static = "http://u:p@1.2.3.4:8080"
    assert proxy_for_region(static, "NL") == static


def test_resolve_rail_proxy_precedence():
    from api_python.upi_link_service import resolve_rail_proxy

    with tempfile.TemporaryDirectory() as empty_root:
        prev_root = os.environ.get("VERIFY_APP_ROOT")
        os.environ["VERIFY_APP_ROOT"] = empty_root
        _clear_proxy_env()
        try:
            os.environ["PAYRAIL_PROXY"] = "http://u__cr.in:p@gw.example.com:10000"
            assert resolve_rail_proxy("ideal") == "http://u__cr.nl:p@gw.example.com:10000"
            assert resolve_rail_proxy("pix") == "http://u__cr.br:p@gw.example.com:10000"

            os.environ["IDEAL_LINK_PROXY"] = "http://dedicated:p@nl.example.com:9000"
            assert resolve_rail_proxy("ideal") == "http://dedicated:p@nl.example.com:9000"

            os.environ["PAYRAIL_PROXY_IDEAL"] = "http://canon:p@nl2.example.com:9000"
            assert resolve_rail_proxy("ideal") == "http://canon:p@nl2.example.com:9000"
        finally:
            _clear_proxy_env()
            if prev_root is None:
                os.environ.pop("VERIFY_APP_ROOT", None)
            else:
                os.environ["VERIFY_APP_ROOT"] = prev_root


def test_spec_amount_max_and_promo_overrides():
    from api_python.rail_specs import GOPAY_SPEC, UPI_SPEC

    assert UPI_SPEC.resolve_amount_max() == 50000
    assert GOPAY_SPEC.resolve_amount_max() is None

    os.environ["PAYRAIL_AMOUNT_MAX_UPI"] = "none"
    os.environ["PAYRAIL_AMOUNT_MAX_GOPAY"] = "50000000"
    os.environ["PAYRAIL_PROMO_UPI"] = "off"
    os.environ["PAYRAIL_PLAN_NAME"] = "chatgptproplan"
    try:
        assert UPI_SPEC.resolve_amount_max() is None
        assert GOPAY_SPEC.resolve_amount_max() == 50000000
        assert UPI_SPEC.resolve_promo_campaign() is None
        assert UPI_SPEC.resolve_promotion_region() is None
        body = UPI_SPEC.checkout_body()
        assert body["plan_name"] == "chatgptproplan"
        assert "promo_campaign" not in body
    finally:
        for k in ("PAYRAIL_AMOUNT_MAX_UPI", "PAYRAIL_AMOUNT_MAX_GOPAY", "PAYRAIL_PROMO_UPI", "PAYRAIL_PLAN_NAME"):
            os.environ.pop(k, None)


def test_http_client_country_locales():
    from api_python.upi_link_service import UpiHttpClient

    for cc, expected_locale in (("IN", "en-IN"), ("NL", "en-NL"), ("BR", "pt-BR"), ("ID", "en-ID"), ("VN", "vi-VN")):
        c = UpiHttpClient("", region=cc)
        try:
            assert c.locale == expected_locale, f"{cc}: {c.locale}"
            assert expected_locale.split("-")[0] in c.accept_language
        finally:
            c.close()


def test_db_rail_id_migration_and_filtering():
    from api_python import db, upi_link_admin_service as admin

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "legacy.sqlite3")
        # Seed a legacy table WITHOUT rail_id column to verify ALTER TABLE migration
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE settings (id TEXT PRIMARY KEY, content TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE upi_link_extractions (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                promo_state TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                long_url TEXT,
                long_url_masked TEXT NOT NULL DEFAULT '',
                currency TEXT NOT NULL DEFAULT 'INR',
                result_message TEXT NOT NULL DEFAULT '',
                result_message_raw TEXT,
                steps_json TEXT,
                debug_json TEXT,
                fail_stage TEXT NOT NULL DEFAULT '',
                amount INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO upi_link_extractions (id, job_id, email, status) VALUES ('oldjob1', 'oldjob1', 'old@example.com', 'completed');
        """)
        conn.commit()
        conn.close()

        prev = os.environ.get("PAYRAIL_DATABASE")
        os.environ["PAYRAIL_DATABASE"] = db_path
        try:
            db.init_database()
            admin.insert_upi_link_record(job_id="j_ideal", rail_id="ideal", user_id="owner", email="nl@example.com", currency="EUR", status="processing")
            admin.finalize_upi_link_record("j_ideal", rail_id="ideal", status="completed", currency="EUR", long_url="https://hooks.stripe.com/redirect/test", amount=2000)

            all_recs = admin.list_upi_link_records()
            assert all_recs["total"] == 2
            ideal_recs = admin.list_upi_link_records(rail="ideal")
            assert ideal_recs["total"] == 1
            assert ideal_recs["items"][0]["rail_id"] == "ideal"
            assert ideal_recs["items"][0]["currency"] == "EUR"
            upi_recs = admin.list_upi_link_records(rail="upi")
            assert upi_recs["total"] == 1
            assert upi_recs["items"][0]["id"] == "oldjob1"
        finally:
            if prev is None:
                os.environ.pop("PAYRAIL_DATABASE", None)
            else:
                os.environ["PAYRAIL_DATABASE"] = prev


def _asgi_call(app, method: str, path: str, *, query: str = "", json_body: dict | None = None, headers: dict[str, str] | None = None):
    import asyncio
    import json

    raw_body = json.dumps(json_body).encode("utf-8") if json_body is not None else b""
    hdr_list = [(b"host", b"localhost")]
    if json_body is not None:
        hdr_list.append((b"content-type", b"application/json"))
        hdr_list.append((b"content-length", str(len(raw_body)).encode()))
    for k, v in (headers or {}).items():
        hdr_list.append((k.lower().encode(), v.encode()))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": hdr_list,
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 8104),
    }

    async def run():
        sent = False
        status = 500
        resp_headers: list[tuple[bytes, bytes]] = []
        chunks: list[bytes] = []

        async def receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": raw_body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(msg):
            nonlocal status, resp_headers
            if msg["type"] == "http.response.start":
                status = msg["status"]
                resp_headers = msg.get("headers", [])
            elif msg["type"] == "http.response.body":
                chunks.append(msg.get("body", b""))

        await app(scope, receive, send)
        raw_out = b"".join(chunks).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw_out) if raw_out else {}
        except json.JSONDecodeError:
            parsed = raw_out
        return status, resp_headers, parsed

    return asyncio.run(run())


def test_fastapi_multi_rail_endpoints():
    from api_python import db
    from api_python.security import hash_password

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "api.sqlite3")
        _clear_proxy_env()
        os.environ["VERIFY_APP_ROOT"] = tmp
        os.environ["PAYRAIL_DATABASE"] = db_path
        os.environ["PAYRAIL_SECRET_KEY"] = "t" * 52
        os.environ["PAYRAIL_PASSWORD_HASH"] = hash_password("pass123")
        os.environ["PAYRAIL_ALLOWED_HOSTS"] = "localhost,127.0.0.1"
        os.environ["PAYRAIL_ALLOW_HTTP"] = "1"
        try:
            import importlib
            import api_python.main as main_mod
            importlib.reload(main_mod)
            db.init_database()

            # Unauthenticated access must be rejected with 401
            st_unauth, _, _ = _asgi_call(main_mod.app, "GET", "/api/config")
            assert st_unauth == 401, f"expected 401 unauth, got {st_unauth}"
            st_unauth_rails, _, _ = _asgi_call(main_mod.app, "GET", "/api/rails")
            assert st_unauth_rails == 401, f"expected 401 unauth rails, got {st_unauth_rails}"

            st, hdrs, data = _asgi_call(main_mod.app, "POST", "/api/auth/login", json_body={"password": "pass123"})
            assert st == 200, f"login failed: {st} {data}"
            csrf = data["csrf_token"]
            cookies = []
            for k, v in hdrs:
                if k.lower() == b"set-cookie":
                    cookies.append(v.decode().split(";", 1)[0])
            cookie_hdr = "; ".join(cookies)
            assert "payrail_session=" in cookie_hdr

            # Missing or bad CSRF token must be rejected with 403
            st_nocsrf, _, _ = _asgi_call(
                main_mod.app,
                "POST",
                "/api/extract",
                headers={"Cookie": cookie_hdr},
                json_body={"access_token": "a.b.c" + "x" * 25, "rail": "ideal"},
            )
            assert st_nocsrf == 403, f"expected 403 without CSRF, got {st_nocsrf}"
            st_badcsrf, _, _ = _asgi_call(
                main_mod.app,
                "POST",
                "/api/extract",
                headers={"Cookie": cookie_hdr, "X-CSRF-Token": "wrong-token"},
                json_body={"access_token": "a.b.c" + "x" * 25, "rail": "ideal"},
            )
            assert st_badcsrf == 403, f"expected 403 with bad CSRF, got {st_badcsrf}"

            st, _, rails_data = _asgi_call(main_mod.app, "GET", "/api/rails", headers={"Cookie": cookie_hdr})
            assert st == 200, rails_data
            rail_ids = [item["rail_id"] for item in rails_data["rails"]]
            assert sorted(rail_ids) == ["gopay", "ideal", "momo", "pix", "upi"]

            st, _, cfg_data = _asgi_call(main_mod.app, "GET", "/api/config", headers={"Cookie": cookie_hdr})
            assert st == 200
            assert len(cfg_data["rails"]) == 5

            # Unsupported rail -> 400
            st, _, _ = _asgi_call(
                main_mod.app,
                "POST",
                "/api/extract",
                headers={"Cookie": cookie_hdr, "X-CSRF-Token": csrf},
                json_body={"access_token": "a.b.c" + "x" * 25, "rail": "unknown"},
            )
            assert st == 400

            # Valid rail without proxy -> 503
            st, _, _ = _asgi_call(
                main_mod.app,
                "POST",
                "/api/extract",
                headers={"Cookie": cookie_hdr, "X-CSRF-Token": csrf},
                json_body={"access_token": "a.b.c" + "x" * 25, "rail": "ideal"},
            )
            assert st == 503

            # Cookie-array JSON and raw cookie string must pass input format gate (not 400)
            os.environ["PAYRAIL_PROXY_IDEAL"] = "http://u:p@nl.example.com:9000"
            try:
                for sample in (
                    '[{"name":"__Secure-next-auth.session-token","value":"' + "x" * 30 + '"}]',
                    "__Secure-next-auth.session-token=" + "y" * 30 + "; Path=/",
                ):
                    st_fmt, _, body_fmt = _asgi_call(
                        main_mod.app,
                        "POST",
                        "/api/extract",
                        headers={"Cookie": cookie_hdr, "X-CSRF-Token": csrf},
                        json_body={"access_token": sample, "rail": "ideal"},
                    )
                    assert "cookie export" not in str(body_fmt), f"format check rejected {sample[:20]}: {st_fmt} {body_fmt}"
            finally:
                os.environ.pop("PAYRAIL_PROXY_IDEAL", None)

            st, _, recs_data = _asgi_call(main_mod.app, "GET", "/api/records", query="rail=ideal", headers={"Cookie": cookie_hdr})
            assert st == 200
            assert recs_data["total"] == 0
        finally:
            _clear_proxy_env()
            for k in ("VERIFY_APP_ROOT", "PAYRAIL_DATABASE", "PAYRAIL_SECRET_KEY", "PAYRAIL_PASSWORD_HASH", "PAYRAIL_ALLOWED_HOSTS", "PAYRAIL_ALLOW_HTTP"):
                os.environ.pop(k, None)


def test_sentinel_quickjs_sanitized_env_and_toggle():
    from pathlib import Path
    import sentinel_quickjs
    from api_python.upi_link_service import _import_build_sentinel_token

    os.environ["PAYRAIL_SECRET_KEY"] = "super-secret-value"
    os.environ["UPI_LINK_PROXY"] = "http://user:pass@proxy:1000"
    try:
        env = sentinel_quickjs._sanitized_node_env(Path("/tmp/sdk.js"), Path("/tmp/q.js"), 10000)
        assert "PAYRAIL_SECRET_KEY" not in env
        assert "UPI_LINK_PROXY" not in env
        assert env["OPENAI_SENTINEL_SDK_FILE"] == "/tmp/sdk.js"
        assert env["OPENAI_SENTINEL_VM_TIMEOUT_MS"] == "10000"
    finally:
        os.environ.pop("PAYRAIL_SECRET_KEY", None)
        os.environ.pop("UPI_LINK_PROXY", None)

    prev = os.environ.get("PAYRAIL_QUICKJS_SENTINEL")
    os.environ["PAYRAIL_QUICKJS_SENTINEL"] = "0"
    try:
        assert _import_build_sentinel_token() is None
    finally:
        if prev is None:
            os.environ.pop("PAYRAIL_QUICKJS_SENTINEL", None)
        else:
            os.environ["PAYRAIL_QUICKJS_SENTINEL"] = prev


def test_stale_job_does_not_execute_worker():
    from api_python import db, upi_link_admin_service as admin, upi_link_service as svc

    with tempfile.TemporaryDirectory() as tmp:
        prev_root = os.environ.get("VERIFY_APP_ROOT")
        prev_db = os.environ.get("PAYRAIL_DATABASE")
        os.environ["VERIFY_APP_ROOT"] = tmp
        os.environ["PAYRAIL_DATABASE"] = os.path.join(tmp, "stale.sqlite3")
        try:
            db.init_database()
            jid = "deadbeef" * 4
            admin.insert_upi_link_record(job_id=jid, rail_id="ideal", status="failed", fail_stage="stale_timeout", result_message="Job timed out")
            svc._set_job({"job_id": jid, "rail_id": "ideal", "status": "failed", "error": "Job timed out", "created_at": 1.0, "updated_at": 1.0})
            # _run_job must exit immediately without touching the already-failed DB record
            svc._run_job(jid, "invalid-token", "http://unused:1", "owner")
            rec = admin.list_upi_link_records(rail="ideal")["items"][0]
            assert rec["status"] == "failed"
            assert rec["fail_stage"] == "stale_timeout"
        finally:
            if prev_root is None:
                os.environ.pop("VERIFY_APP_ROOT", None)
            else:
                os.environ["VERIFY_APP_ROOT"] = prev_root
            if prev_db is None:
                os.environ.pop("PAYRAIL_DATABASE", None)
            else:
                os.environ["PAYRAIL_DATABASE"] = prev_db


def test_token_and_session_cookie_parsing():
    import json
    from api_python.upi_link_service import _extract_session_token_from_raw, normalize_access_token

    jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1MSJ9.sigpart1234567890"
    assert normalize_access_token(jwt) == jwt
    assert normalize_access_token(f"Bearer {jwt}") == jwt
    assert normalize_access_token(json.dumps({"accessToken": jwt, "sessionToken": "sess_abc"})) == jwt
    assert _extract_session_token_from_raw(json.dumps({"accessToken": jwt, "sessionToken": "sess_abc"})) == "sess_abc"

    # sessionToken-only JSON must NOT leak sessionToken or email as accessToken
    only_sess = json.dumps({"user": {"email": "u@example.com"}, "sessionToken": "sess_only_123"})
    assert normalize_access_token(only_sess) == ""
    assert _extract_session_token_from_raw(only_sess) == "sess_only_123"

    # Browser cookie-export JSON array
    cookie_export = json.dumps([
        {"name": "oai-did", "value": "did-1"},
        {"name": "__Secure-next-auth.session-token", "value": "cookie_tok_xyz"},
    ])
    assert normalize_access_token(cookie_export) == ""
    assert _extract_session_token_from_raw(cookie_export) == "cookie_tok_xyz"

    # Raw Cookie header string
    cookie_hdr = "oai-did=123; __Secure-next-auth.session-token=hdr_tok_999; Path=/"
    assert normalize_access_token(cookie_hdr) == ""
    assert _extract_session_token_from_raw(cookie_hdr) == "hdr_tok_999"


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
