"""End-to-end tests for the API rack: auth, metering, billing and every service."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SAAS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SAAS))

from saascore.app import create_app  # noqa: E402
from saascore.store import PLANS, Store  # noqa: E402
from serve import SERVICES, load_spec  # noqa: E402


@pytest.fixture
def store(tmp_path) -> Store:
    return Store(tmp_path / "test.db")


def client_for(name: str, store: Store) -> TestClient:
    return TestClient(create_app(load_spec(name), store=store))


@pytest.fixture
def key(store: Store) -> str:
    raw, _ = store.create_key(plan="pro", label="test", service="*")
    return raw


def auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


# --------------------------------------------------------------------- auth


class TestAuth:
    def test_missing_key_is_401(self, store):
        response = client_for("colorkit", store).post(
            "/v1/color/convert", json={"color": "#ff0000"}
        )
        assert response.status_code == 401

    def test_bad_key_is_401(self, store):
        response = client_for("colorkit", store).post(
            "/v1/color/convert", json={"color": "#ff0000"}, headers=auth("sk_live_nope")
        )
        assert response.status_code == 401

    def test_valid_key_works(self, store, key):
        response = client_for("colorkit", store).post(
            "/v1/color/convert", json={"color": "#ff0000"}, headers=auth(key)
        )
        assert response.status_code == 200

    def test_x_api_key_header_also_works(self, store, key):
        response = client_for("colorkit", store).post(
            "/v1/color/convert", json={"color": "#ff0000"}, headers={"X-API-Key": key}
        )
        assert response.status_code == 200

    def test_revoked_key_is_rejected(self, store):
        raw, record = store.create_key(plan="pro")
        store.revoke(record.id)
        response = client_for("colorkit", store).post(
            "/v1/color/convert", json={"color": "#f00"}, headers=auth(raw)
        )
        assert response.status_code == 401

    def test_key_scoped_to_another_service_is_403(self, store):
        raw, _ = store.create_key(plan="pro", service="qr")
        response = client_for("colorkit", store).post(
            "/v1/color/convert", json={"color": "#f00"}, headers=auth(raw)
        )
        assert response.status_code == 403

    def test_plaintext_key_is_never_stored(self, store, key):
        with store._lock:
            rows = store._conn.execute("SELECT key_hash FROM keys").fetchall()
        assert all(key not in row["key_hash"] for row in rows)

    def test_quota_is_enforced(self, store):
        raw, _ = store.create_key(plan="free")
        client = client_for("colorkit", store)
        # Free plan allows 500 calls; burn them via the store, then call once.
        record = store.get_key(raw)
        for _ in range(PLANS["free"]["quota"]):
            store.record_call(record.id, "/v1/color/convert")
        response = client.post("/v1/color/convert", json={"color": "#f00"}, headers=auth(raw))
        assert response.status_code == 402
        assert "quota" in response.json()["detail"].lower()

    def test_rate_limit_returns_429(self, store):
        raw, _ = store.create_key(plan="free")  # 10 rpm
        client = client_for("colorkit", store)
        codes = [
            client.post("/v1/color/convert", json={"color": "#f00"}, headers=auth(raw)).status_code
            for _ in range(13)
        ]
        assert 429 in codes
        assert codes.count(200) == PLANS["free"]["rpm"]

    def test_quota_headers_are_present(self, store, key):
        response = client_for("colorkit", store).post(
            "/v1/color/convert", json={"color": "#f00"}, headers=auth(key)
        )
        assert response.headers["X-Plan"] == "pro"
        assert int(response.headers["X-Quota-Remaining"]) < int(response.headers["X-Quota-Limit"])

    def test_usage_endpoint_reports_calls(self, store, key):
        client = client_for("colorkit", store)
        client.post("/v1/color/convert", json={"color": "#f00"}, headers=auth(key))
        usage = client.get("/v1/usage", headers=auth(key)).json()
        assert usage["plan"] == "pro"
        assert usage["used"] >= 1


class TestAdmin:
    def test_admin_requires_a_token(self, store, monkeypatch):
        monkeypatch.setenv("SAAS_ADMIN_TOKEN", "secret")
        client = client_for("colorkit", store)
        assert client.post("/admin/keys").status_code == 403
        ok = client.post("/admin/keys", headers={"X-Admin-Token": "secret"})
        assert ok.status_code == 200
        assert ok.json()["api_key"].startswith("sk_live_")

    def test_admin_unset_is_503(self, store, monkeypatch):
        monkeypatch.delenv("SAAS_ADMIN_TOKEN", raising=False)
        assert client_for("colorkit", store).post(
            "/admin/keys", headers={"X-Admin-Token": "x"}
        ).status_code == 503

    def test_unknown_plan_is_rejected(self, store, monkeypatch):
        monkeypatch.setenv("SAAS_ADMIN_TOKEN", "secret")
        response = client_for("colorkit", store).post(
            "/admin/keys", params={"plan": "unlimited"}, headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 400


class TestBilling:
    def test_plans_are_public(self, store):
        response = client_for("qr", store).get("/v1/billing/plans")
        assert response.status_code == 200
        assert {p["name"] for p in response.json()["plans"]} == set(PLANS)

    def test_free_plan_cannot_be_bought(self, store, key):
        response = client_for("qr", store).post(
            "/v1/billing/upgrade", params={"plan": "free"}, headers=auth(key)
        )
        assert response.status_code == 400

    def test_upgrade_without_credentials_is_503(self, store, key, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        response = client_for("qr", store).post(
            "/v1/billing/upgrade", params={"plan": "pro"}, headers=auth(key)
        )
        assert response.status_code == 503

    def test_paid_invoice_upgrades_the_key_once(self, store):
        _, record = store.create_key(plan="free")
        store.create_invoice(
            key_id=record.id, provider="stripe", external_id="cs_1",
            plan="pro", amount=29.0, currency="EUR",
        )
        upgraded = store.mark_invoice_paid("stripe", "cs_1", {"id": "cs_1"})
        assert upgraded is not None and upgraded.plan == "pro"
        # A replayed webhook must be a no-op.
        assert store.mark_invoice_paid("stripe", "cs_1", {"id": "cs_1"}) is None

    def test_unsigned_crypto_webhook_is_rejected(self, store, monkeypatch):
        monkeypatch.setenv("CRYPTOBOT_TOKEN", "tok")
        response = client_for("qr", store).post(
            "/v1/billing/webhook/cryptobot",
            content=b'{"update_type":"invoice_paid"}',
            headers={"crypto-pay-api-signature": "bad"},
        )
        assert response.status_code == 400


# ----------------------------------------------------------------- services


class TestMeta:
    @pytest.mark.parametrize("name", sorted(SERVICES))
    def test_every_service_has_health_docs_and_landing(self, name, store):
        client = client_for(name, store)
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["service"] == load_spec(name).name
        assert client.get("/").status_code == 200
        assert client.get("/openapi.json").status_code == 200

    @pytest.mark.parametrize("name", sorted(SERVICES))
    def test_every_service_rejects_anonymous_calls(self, name, store):
        """No endpoint may be usable without a key (except public redirects)."""
        client = client_for(name, store)
        schema = client.get("/openapi.json").json()
        for path, methods in schema["paths"].items():
            if not path.startswith("/v1/") or path.startswith("/v1/billing"):
                continue
            for method in methods:
                response = client.request(method.upper(), path.replace("{code}", "u4pruy"))
                assert response.status_code in {401, 422}, f"{method.upper()} {path} leaked"


class TestQr:
    def test_png_is_returned(self, store, key):
        response = client_for("qr", store).post(
            "/v1/qr", json={"data": "https://example.com", "size": 256}, headers=auth(key)
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_svg_is_returned(self, store, key):
        response = client_for("qr", store).post(
            "/v1/qr", json={"data": "hello", "format": "svg"}, headers=auth(key)
        )
        assert response.status_code == 200
        assert b"<svg" in response.content

    def test_bad_colour_is_400(self, store, key):
        response = client_for("qr", store).post(
            "/v1/qr", json={"data": "x", "fill": "red"}, headers=auth(key)
        )
        assert response.status_code == 400

    def test_base64_variant(self, store, key):
        response = client_for("qr", store).post(
            "/v1/qr/base64", json={"data": "hello"}, headers=auth(key)
        )
        assert response.json()["data_uri"].startswith("data:image/png;base64,")


class TestOgImage:
    def test_card_renders(self, store, key):
        response = client_for("ogimage", store).post(
            "/v1/og",
            json={"title": "Ship faster", "subtitle": "No browser", "theme": "indigo"},
            headers=auth(key),
        )
        assert response.status_code == 200
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_unknown_theme_is_400(self, store, key):
        response = client_for("ogimage", store).post(
            "/v1/og", json={"title": "x", "theme": "neon"}, headers=auth(key)
        )
        assert response.status_code == 400


class TestShortlink:
    def test_create_and_follow(self, store, key):
        client = client_for("shortlink", store)
        from services.shortlink import build_public_router

        client.app.include_router(build_public_router())

        created = client.post(
            "/v1/links", json={"url": "https://example.com/page"}, headers=auth(key)
        )
        assert created.status_code == 200
        slug = created.json()["slug"]

        redirect = client.get(f"/{slug}", follow_redirects=False)
        assert redirect.status_code == 302
        assert redirect.headers["location"] == "https://example.com/page"

        stats = client.get(f"/v1/links/{slug}", headers=auth(key)).json()
        assert stats["clicks"] == 1

    def test_private_targets_are_refused(self, store, key):
        for target in ("http://localhost/x", "http://192.168.1.1/", "http://169.254.169.254/"):
            response = client_for("shortlink", store).post(
                "/v1/links", json={"url": target}, headers=auth(key)
            )
            assert response.status_code == 400, target

    def test_duplicate_slug_is_409(self, store, key):
        client = client_for("shortlink", store)
        body = {"url": "https://example.com", "slug": "mine"}
        assert client.post("/v1/links", json=body, headers=auth(key)).status_code == 200
        assert client.post("/v1/links", json=body, headers=auth(key)).status_code == 409


class TestMailcheck:
    def test_typo_gets_a_suggestion(self, store, key):
        result = client_for("mailcheck", store).post(
            "/v1/email/check",
            json={"email": "user@gmial.com", "resolve_domain": False},
            headers=auth(key),
        ).json()
        assert result["suggestion"] == "user@gmail.com"

    def test_disposable_is_flagged(self, store, key):
        result = client_for("mailcheck", store).post(
            "/v1/email/check",
            json={"email": "a@mailinator.com", "resolve_domain": False},
            headers=auth(key),
        ).json()
        assert result["disposable"] is True
        assert result["deliverable"] is False

    def test_role_account_is_flagged(self, store, key):
        result = client_for("mailcheck", store).post(
            "/v1/email/check",
            json={"email": "support@acme.io", "resolve_domain": False},
            headers=auth(key),
        ).json()
        assert result["role_account"] is True

    def test_broken_syntax_scores_low(self, store, key):
        result = client_for("mailcheck", store).post(
            "/v1/email/check", json={"email": "not-an-email", "resolve_domain": False},
            headers=auth(key),
        ).json()
        assert result["valid_syntax"] is False
        assert result["score"] < 50


class TestAuthkit:
    def test_totp_round_trip(self, store, key):
        client = client_for("authkit", store)
        created = client.post(
            "/v1/totp/new", json={"account": "user@acme.io"}, headers=auth(key)
        ).json()
        verified = client.post(
            "/v1/totp/verify",
            json={"secret": created["secret"], "code": created["current_code"]},
            headers=auth(key),
        ).json()
        assert verified["valid"] is True

    def test_wrong_totp_code_fails(self, store, key):
        client = client_for("authkit", store)
        created = client.post(
            "/v1/totp/new", json={"account": "u@a.io"}, headers=auth(key)
        ).json()
        result = client.post(
            "/v1/totp/verify", json={"secret": created["secret"], "code": "000000"},
            headers=auth(key),
        ).json()
        assert result["valid"] is False

    def test_passphrase_generation(self, store, key):
        result = client_for("authkit", store).post(
            "/v1/password/generate",
            json={"style": "passphrase", "words": 4, "count": 3},
            headers=auth(key),
        ).json()
        assert len(result["passwords"]) == 3
        assert all(p["entropy_bits"] > 0 for p in result["passwords"])

    def test_common_password_scores_very_weak(self, store, key):
        result = client_for("authkit", store).post(
            "/v1/password/strength", json={"password": "password"}, headers=auth(key)
        ).json()
        assert result["verdict"] == "very weak"

    def test_long_random_password_scores_strong(self, store, key):
        result = client_for("authkit", store).post(
            "/v1/password/strength",
            json={"password": "T7#kq2Wm!zP9vL4$xR6b"}, headers=auth(key),
        ).json()
        assert result["verdict"] in {"strong", "very strong"}


class TestTextkit:
    def test_cyrillic_slug(self, store, key):
        result = client_for("textkit", store).post(
            "/v1/text/slug", json={"text": "Привет, мир! Как дела?"}, headers=auth(key)
        ).json()
        assert result["slug"] == "privet-mir-kak-dela"

    def test_german_umlauts(self, store, key):
        result = client_for("textkit", store).post(
            "/v1/text/slug", json={"text": "Über größe Straße"}, headers=auth(key)
        ).json()
        assert result["slug"] == "ueber-groesse-strasse"

    def test_analyze_counts_and_scores(self, store, key):
        text = "The cat sat on the mat. The dog barked loudly. Cats and dogs are pets."
        result = client_for("textkit", store).post(
            "/v1/text/analyze", json={"text": text}, headers=auth(key)
        ).json()
        assert result["sentences"] == 3
        assert result["words"] > 10
        assert 0 <= result["flesch_reading_ease"] <= 100

    def test_summarize_shortens(self, store, key):
        text = " ".join(
            f"Sentence number {i} discusses payment processing and revenue growth."
            for i in range(12)
        )
        result = client_for("textkit", store).post(
            "/v1/text/summarize", json={"text": text, "sentences": 3}, headers=auth(key)
        ).json()
        assert result["sentences"] <= 3
        assert len(result["summary"]) < len(text)

    def test_case_conversion(self, store, key):
        result = client_for("textkit", store).post(
            "/v1/text/case", params={"text": "hello world example", "style": "camel"},
            headers=auth(key),
        ).json()
        assert result["result"] == "helloWorldExample"
        assert result["all_styles"]["pascal"] == "HelloWorldExample"


class TestDevkit:
    def test_uuid7_is_time_ordered(self, store, key):
        """Even 200 IDs minted inside one millisecond must sort correctly."""
        result = client_for("devkit", store).post(
            "/v1/id/generate", json={"kind": "uuid7", "count": 200}, headers=auth(key)
        ).json()
        assert result["ids"] == sorted(result["ids"])
        assert result["sortable"] is True
        assert all(uid[14] == "7" for uid in result["ids"])  # version nibble

    def test_ulid_length(self, store, key):
        result = client_for("devkit", store).post(
            "/v1/id/generate", json={"kind": "ulid", "count": 3}, headers=auth(key)
        ).json()
        assert all(len(i) == 26 for i in result["ids"])

    def test_known_sha256(self, store, key):
        result = client_for("devkit", store).post(
            "/v1/hash", json={"text": "abc", "algorithm": "sha256"}, headers=auth(key)
        ).json()
        assert result["digest"] == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )

    def test_jwt_signature_verification(self, store, key):
        import base64
        import hashlib
        import hmac
        import json as js

        def b64(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).decode().rstrip("=")

        header = b64(js.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = b64(js.dumps({"sub": "42", "exp": 9999999999}).encode())
        signature = b64(
            hmac.new(b"topsecret", f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        token = f"{header}.{payload}.{signature}"

        client = client_for("devkit", store)
        good = client.post(
            "/v1/jwt/decode", json={"token": token, "secret": "topsecret"}, headers=auth(key)
        ).json()
        assert good["signature_verified"] is True
        assert good["expired"] is False
        assert good["payload"]["sub"] == "42"

        bad = client.post(
            "/v1/jwt/decode", json={"token": token, "secret": "wrong"}, headers=auth(key)
        ).json()
        assert bad["signature_verified"] is False

    def test_cron_weekday_schedule(self, store, key):
        result = client_for("devkit", store).post(
            "/v1/cron/next",
            json={"expression": "0 9 * * 1-5", "count": 5, "start": "2026-01-01T00:00:00Z"},
            headers=auth(key),
        ).json()
        assert len(result["next_runs"]) == 5
        for run in result["next_runs"]:
            assert run.endswith("09:00:00+00:00")

    def test_bad_cron_is_400(self, store, key):
        response = client_for("devkit", store).post(
            "/v1/cron/next", json={"expression": "not a cron"}, headers=auth(key)
        )
        assert response.status_code == 400


class TestDatakit:
    def test_csv_to_json(self, store, key):
        response = client_for("datakit", store).post(
            "/v1/data/convert",
            json={"data": "name,age\nAlice,30\nBob,25", "source": "csv", "target": "json"},
            headers=auth(key),
        )
        assert response.status_code == 200
        import json as js

        rows = js.loads(response.text)
        assert rows[0]["name"] == "Alice"
        assert len(rows) == 2

    def test_json_to_csv_unions_keys(self, store, key):
        response = client_for("datakit", store).post(
            "/v1/data/convert",
            json={"data": '[{"a":1},{"b":2}]', "source": "json", "target": "csv"},
            headers=auth(key),
        )
        assert "a,b" in response.text

    def test_flatten_nested(self, store, key):
        result = client_for("datakit", store).post(
            "/v1/data/flatten",
            json={"data": '{"user":{"name":"Ann","tags":["a","b"]}}'},
            headers=auth(key),
        ).json()
        assert result["flat"]["user.name"] == "Ann"
        assert result["flat"]["user.tags[0]"] == "a"

    def test_malformed_input_is_400(self, store, key):
        response = client_for("datakit", store).post(
            "/v1/data/convert",
            json={"data": "{not json", "source": "json", "target": "yaml"},
            headers=auth(key),
        )
        assert response.status_code == 400


class TestColorkit:
    def test_conversion(self, store, key):
        result = client_for("colorkit", store).post(
            "/v1/color/convert", json={"color": "#ff0000"}, headers=auth(key)
        ).json()
        assert result["rgb"] == {"r": 255, "g": 0, "b": 0}
        assert result["hsl"]["h"] == 0.0

    def test_shorthand_hex(self, store, key):
        result = client_for("colorkit", store).post(
            "/v1/color/convert", json={"color": "#f00"}, headers=auth(key)
        ).json()
        assert result["hex"] == "#ff0000"

    def test_contrast_known_values(self, store, key):
        client = client_for("colorkit", store)
        black_on_white = client.post(
            "/v1/color/contrast",
            json={"foreground": "#000000", "background": "#ffffff"}, headers=auth(key),
        ).json()
        assert black_on_white["ratio"] == 21.0
        assert black_on_white["verdict"] == "AAA"

        failing = client.post(
            "/v1/color/contrast",
            json={"foreground": "#aaaaaa", "background": "#ffffff"}, headers=auth(key),
        ).json()
        assert failing["passes_aa"] is False

    def test_palette_size(self, store, key):
        result = client_for("colorkit", store).post(
            "/v1/color/palette",
            json={"color": "#3366cc", "scheme": "analogous", "count": 5}, headers=auth(key),
        ).json()
        assert len(result["colors"]) == 5


class TestGeokit:
    def test_moscow_to_saint_petersburg(self, store, key):
        result = client_for("geokit", store).post(
            "/v1/geo/distance",
            json={"from": {"lat": 55.7558, "lon": 37.6173},
                  "to": {"lat": 59.9343, "lon": 30.3351}},
            headers=auth(key),
        ).json()
        # The great-circle distance is about 634 km.
        assert 630 < result["distance_km"] < 640
        assert result["compass"] in {"NW", "NNW", "WNW"}

    def test_geohash_round_trip(self, store, key):
        client = client_for("geokit", store)
        encoded = client.post(
            "/v1/geo/geohash", json={"lat": 55.7558, "lon": 37.6173, "precision": 9},
            headers=auth(key),
        ).json()
        decoded = client.get(f"/v1/geo/geohash/{encoded['geohash']}", headers=auth(key)).json()
        assert abs(decoded["center"]["lat"] - 55.7558) < 0.01
        assert abs(decoded["center"]["lon"] - 37.6173) < 0.01

    def test_point_in_polygon(self, store, key):
        square = [
            {"lat": 0, "lon": 0}, {"lat": 0, "lon": 10},
            {"lat": 10, "lon": 10}, {"lat": 10, "lon": 0},
        ]
        client = client_for("geokit", store)
        inside = client.post(
            "/v1/geo/contains", json={"point": {"lat": 5, "lon": 5}, "polygon": square},
            headers=auth(key),
        ).json()
        outside = client.post(
            "/v1/geo/contains", json={"point": {"lat": 20, "lon": 20}, "polygon": square},
            headers=auth(key),
        ).json()
        assert inside["contains"] is True
        assert outside["contains"] is False

    def test_bbox_clamps_at_the_pole(self, store, key):
        result = client_for("geokit", store).post(
            "/v1/geo/bbox", json={"center": {"lat": 89.9, "lon": 0}, "radius_km": 100},
            headers=auth(key),
        ).json()
        assert result["max_lat"] <= 90.0
        assert -180.0 <= result["min_lon"] <= result["max_lon"] <= 180.0


class TestMoneykit:
    def test_german_vat_added(self, store, key):
        result = client_for("moneykit", store).post(
            "/v1/money/vat", json={"amount": 100, "country": "DE"}, headers=auth(key)
        ).json()
        assert result["net"] == 100.0
        assert result["vat"] == 19.0
        assert result["gross"] == 119.0

    def test_vat_extracted_from_gross(self, store, key):
        result = client_for("moneykit", store).post(
            "/v1/money/vat",
            json={"amount": 119, "country": "DE", "amount_includes_vat": True},
            headers=auth(key),
        ).json()
        assert result["net"] == 100.0
        assert result["vat"] == 19.0

    def test_valid_iban(self, store, key):
        result = client_for("moneykit", store).post(
            "/v1/money/iban", json={"iban": "DE89 3704 0044 0532 0130 00"}, headers=auth(key)
        ).json()
        assert result["valid"] is True
        assert result["country"] == "DE"

    def test_iban_with_a_typo_fails_checksum(self, store, key):
        result = client_for("moneykit", store).post(
            "/v1/money/iban", json={"iban": "DE89370400440532013001"}, headers=auth(key)
        ).json()
        assert result["valid"] is False

    def test_luhn_and_brand(self, store, key):
        client = client_for("moneykit", store)
        visa = client.post(
            "/v1/money/card", json={"number": "4111 1111 1111 1111"}, headers=auth(key)
        ).json()
        assert visa["valid"] is True and visa["brand"] == "Visa"

        broken = client.post(
            "/v1/money/card", json={"number": "4111111111111112"}, headers=auth(key)
        ).json()
        assert broken["valid"] is False

    def test_card_number_is_masked(self, store, key):
        result = client_for("moneykit", store).post(
            "/v1/money/card", json={"number": "4111111111111111"}, headers=auth(key)
        ).json()
        assert result["masked"].endswith("1111")
        assert "*" in result["masked"]

    def test_invoice_number_pattern(self, store, key):
        result = client_for("moneykit", store).post(
            "/v1/money/invoice-number",
            json={"prefix": "ACME", "sequence": 42, "date": "2026-03-09"}, headers=auth(key),
        ).json()
        assert result["invoice_number"] == "ACME-2026-00042"


class TestTimekit:
    def test_timezone_conversion(self, store, key):
        result = client_for("timekit", store).post(
            "/v1/time/convert",
            json={"datetime": "2026-07-01T12:00:00", "from_tz": "UTC",
                  "to_tz": "Europe/Moscow"},
            headers=auth(key),
        ).json()
        assert result["converted"].startswith("2026-07-01T15:00:00")

    def test_dst_is_reported(self, store, key):
        result = client_for("timekit", store).post(
            "/v1/time/convert",
            json={"datetime": "2026-07-01T12:00:00Z", "to_tz": "Europe/Berlin"},
            headers=auth(key),
        ).json()
        assert result["is_dst"] is True

    def test_unknown_timezone_is_400(self, store, key):
        response = client_for("timekit", store).post(
            "/v1/time/convert",
            json={"datetime": "2026-01-01T00:00:00", "to_tz": "Mars/Olympus"},
            headers=auth(key),
        )
        assert response.status_code == 400

    def test_business_days_between_dates(self, store, key):
        result = client_for("timekit", store).post(
            "/v1/time/business-days",
            json={"start": "2026-01-05", "end": "2026-01-09"}, headers=auth(key),
        ).json()
        assert result["business_days"] == 5  # Monday to Friday

    def test_business_days_skip_holidays(self, store, key):
        result = client_for("timekit", store).post(
            "/v1/time/business-days",
            json={"start": "2026-01-05", "end": "2026-01-09", "holidays": ["2026-01-07"]},
            headers=auth(key),
        ).json()
        assert result["business_days"] == 4

    def test_russian_plurals(self, store, key):
        client = client_for("timekit", store)
        one = client.post(
            "/v1/time/humanize", json={"seconds": 86400, "language": "ru", "precision": 1},
            headers=auth(key),
        ).json()
        assert one["human"] == "1 день"

        five = client.post(
            "/v1/time/humanize", json={"seconds": 86400 * 5, "language": "ru", "precision": 1},
            headers=auth(key),
        ).json()
        assert five["human"] == "5 дней"

    def test_iso_duration(self, store, key):
        result = client_for("timekit", store).post(
            "/v1/time/humanize", json={"seconds": 3661}, headers=auth(key)
        ).json()
        assert result["iso_duration"] == "PT1H1M1S"


class TestImgtool:
    def _png(self) -> bytes:
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (400, 300), (10, 120, 200)).save(buffer, format="PNG")
        return buffer.getvalue()

    def test_info(self, store, key):
        response = client_for("imgtool", store).post(
            "/v1/image/info", files={"file": ("a.png", self._png(), "image/png")},
            headers=auth(key),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["width"] == 400 and body["height"] == 300

    def test_resize_cover_crops_exactly(self, store, key):
        import io

        from PIL import Image

        response = client_for("imgtool", store).post(
            "/v1/image/resize?width=100&height=100&fit=cover&format=png",
            files={"file": ("a.png", self._png(), "image/png")},
            headers=auth(key),
        )
        assert response.status_code == 200
        assert Image.open(io.BytesIO(response.content)).size == (100, 100)

    def test_convert_to_jpeg_flattens_alpha(self, store, key):
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGBA", (50, 50), (255, 0, 0, 128)).save(buffer, format="PNG")
        response = client_for("imgtool", store).post(
            "/v1/image/convert?format=jpeg",
            files={"file": ("a.png", buffer.getvalue(), "image/png")},
            headers=auth(key),
        )
        assert response.status_code == 200
        assert Image.open(io.BytesIO(response.content)).mode == "RGB"

    def test_garbage_upload_is_400(self, store, key):
        response = client_for("imgtool", store).post(
            "/v1/image/info", files={"file": ("a.png", b"not an image", "image/png")},
            headers=auth(key),
        )
        assert response.status_code == 400
