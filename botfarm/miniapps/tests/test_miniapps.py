"""Tests for the Mini App platform.

The bulk of these are about `initData`. It is the only thing standing between
a Mini App and total impersonation, so it gets adversarial treatment: forged
hashes, replayed payloads, swapped users, wrong bot tokens, tampered fields.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from miniapps.core.auth import (  # noqa: E402
    AuthError,
    build_init_data,
    sign_init_data,
    verify_init_data,
)
from miniapps.core.server import APPS_DIR, available_apps, create_app  # noqa: E402
from miniapps.core.store import AppStore  # noqa: E402

TOKEN = "123456:AA-test-bot-token"
OTHER_TOKEN = "999999:BB-different-token"


@pytest.fixture
def store(tmp_path) -> AppStore:
    return AppStore(tmp_path / "mini.db")


@pytest.fixture
def client(store) -> TestClient:
    return TestClient(create_app(store=store, bot_token=TOKEN))


def auth_header(**kw) -> dict:
    return {"X-Init-Data": build_init_data(TOKEN, **kw)}


# ------------------------------------------------------------------- initData


class TestInitDataVerification:
    def test_valid_payload_is_accepted(self):
        data = build_init_data(TOKEN, {"id": 42, "first_name": "Ann", "username": "ann"})
        result = verify_init_data(data, TOKEN)
        assert result.user.id == 42
        assert result.user.username == "ann"
        assert result.user.display_name == "Ann"

    def test_empty_payload_is_rejected(self):
        with pytest.raises(AuthError, match="empty"):
            verify_init_data("", TOKEN)

    def test_missing_hash_is_rejected(self):
        payload = urlencode({"user": '{"id":1}', "auth_date": str(int(time.time()))})
        with pytest.raises(AuthError, match="no hash"):
            verify_init_data(payload, TOKEN)

    def test_forged_hash_is_rejected(self):
        fields = {"user": '{"id":1}', "auth_date": str(int(time.time())), "hash": "deadbeef"}
        with pytest.raises(AuthError, match="signature"):
            verify_init_data(urlencode(fields), TOKEN)

    def test_payload_signed_with_another_token_is_rejected(self):
        """A Mini App must not accept a payload minted for a different bot."""
        data = build_init_data(OTHER_TOKEN, {"id": 1, "first_name": "X"})
        with pytest.raises(AuthError, match="signature"):
            verify_init_data(data, TOKEN)

    def test_tampering_with_the_user_invalidates_the_hash(self):
        """The core attack: swap the user id, keep the captured signature."""
        original = build_init_data(TOKEN, {"id": 111, "first_name": "Victim"})
        tampered = original.replace("111", "222")
        assert tampered != original
        with pytest.raises(AuthError, match="signature"):
            verify_init_data(tampered, TOKEN)

    def test_adding_a_field_invalidates_the_hash(self):
        data = build_init_data(TOKEN, {"id": 1, "first_name": "A"})
        with pytest.raises(AuthError, match="signature"):
            verify_init_data(data + "&is_admin=true", TOKEN)

    def test_stale_payload_is_rejected(self):
        old = int(time.time()) - 48 * 3600
        data = build_init_data(TOKEN, {"id": 1, "first_name": "A"}, auth_date=old)
        with pytest.raises(AuthError, match="old"):
            verify_init_data(data, TOKEN)

    def test_stale_payload_passes_when_max_age_disabled(self):
        old = int(time.time()) - 48 * 3600
        data = build_init_data(TOKEN, {"id": 1, "first_name": "A"}, auth_date=old)
        assert verify_init_data(data, TOKEN, max_age=0).user.id == 1

    def test_future_payload_is_rejected(self):
        future = int(time.time()) + 9999
        data = build_init_data(TOKEN, {"id": 1, "first_name": "A"}, auth_date=future)
        with pytest.raises(AuthError, match="future"):
            verify_init_data(data, TOKEN)

    def test_payload_without_user_is_rejected(self):
        fields = {"auth_date": str(int(time.time()))}
        fields["hash"] = sign_init_data(fields, TOKEN)
        with pytest.raises(AuthError, match="no user"):
            verify_init_data(urlencode(fields), TOKEN)

    def test_missing_auth_date_is_rejected(self):
        fields = {"user": '{"id":1}'}
        fields["hash"] = sign_init_data(fields, TOKEN)
        with pytest.raises(AuthError, match="auth_date"):
            verify_init_data(urlencode(fields), TOKEN)

    def test_unset_server_token_is_rejected(self):
        data = build_init_data(TOKEN, {"id": 1, "first_name": "A"})
        with pytest.raises(AuthError, match="BOT_TOKEN"):
            verify_init_data(data, "")

    def test_blank_fields_are_kept_in_the_check_string(self):
        """Dropping an empty value would break a legitimate Telegram payload."""
        data = build_init_data(TOKEN, {"id": 1, "first_name": "A"}, start_param="")
        assert verify_init_data(data, TOKEN).start_param == ""

    def test_start_param_survives_verification(self):
        data = build_init_data(TOKEN, {"id": 7, "first_name": "A"}, start_param="table12")
        assert verify_init_data(data, TOKEN).start_param == "table12"

    def test_age_is_reported(self):
        data = build_init_data(TOKEN, {"id": 1, "first_name": "A"},
                               auth_date=int(time.time()) - 120)
        assert 110 <= verify_init_data(data, TOKEN).age_seconds <= 130


# ----------------------------------------------------------------------- API


class TestApi:
    def test_config_requires_auth(self, client):
        assert client.get("/api/shop/config").status_code == 401

    def test_config_rejects_a_forged_header(self, client):
        response = client.get("/api/shop/config", headers={"X-Init-Data": "user=%7B%22id%22%3A1%7D&hash=x"})
        assert response.status_code == 401

    def test_config_returns_the_verified_user(self, client):
        response = client.get(
            "/api/shop/config",
            headers=auth_header(user={"id": 555, "first_name": "Иван", "username": "ivan"}),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == 555
        assert body["user"]["name"] == "Иван"
        assert body["app"]["catalog"]

    def test_unknown_app_is_404(self, client):
        assert client.get("/api/nope/config", headers=auth_header()).status_code == 404

    def test_path_traversal_in_app_name_is_blocked(self, client):
        for evil in ["..", ".hidden"]:
            response = client.get(f"/api/{evil}/config", headers=auth_header())
            assert response.status_code in {400, 404}, evil

    def test_state_round_trip_is_per_user(self, client):
        a = auth_header(user={"id": 1, "first_name": "A"})
        b = auth_header(user={"id": 2, "first_name": "B"})

        client.post("/api/loyalty/state", json={"points": 500}, headers=a)
        client.post("/api/loyalty/state", json={"points": 10}, headers=b)

        assert client.get("/api/loyalty/state", headers=a).json()["state"]["points"] == 500
        assert client.get("/api/loyalty/state", headers=b).json()["state"]["points"] == 10

    def test_oversized_state_is_rejected(self, client):
        big = {"blob": "x" * 70_000}
        response = client.post("/api/shop/state", json=big, headers=auth_header())
        assert response.status_code == 413

    def test_submission_is_recorded(self, client, store):
        response = client.post(
            "/api/shop/submit",
            json={"kind": "order", "items": [{"sku": "basic", "qty": 1}], "total": 480},
            headers=auth_header(user={"id": 900, "first_name": "Buyer"}),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "received"

        rows = store.list_submissions("shop")
        assert len(rows) == 1
        assert rows[0]["tg_id"] == 900
        assert rows[0]["payload"]["total"] == 480

    def test_submission_flood_is_throttled(self, client):
        header = auth_header(user={"id": 901, "first_name": "Spam"})
        codes = [
            client.post("/api/shop/submit", json={"kind": "order"}, headers=header).status_code
            for _ in range(8)
        ]
        assert 429 in codes
        assert codes.count(200) == 5

    def test_submissions_feed_is_owner_only(self, client, store, tmp_path):
        header = auth_header(user={"id": 777, "first_name": "Nosy"})
        assert client.get("/api/shop/submissions", headers=header).status_code == 403

    def test_submissions_feed_visible_to_admin(self, tmp_path, store, monkeypatch):
        """The owner id comes from the manifest, never from the client."""
        manifest = json.loads((APPS_DIR / "shop" / "app.json").read_text(encoding="utf-8"))
        manifest["admin"] = [4242]
        backup = (APPS_DIR / "shop" / "app.json").read_text(encoding="utf-8")
        (APPS_DIR / "shop" / "app.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        try:
            client = TestClient(create_app(store=store, bot_token=TOKEN))
            client.post("/api/shop/submit", json={"kind": "order"},
                        headers=auth_header(user={"id": 5, "first_name": "B"}))
            ok = client.get(
                "/api/shop/submissions",
                headers=auth_header(user={"id": 4242, "first_name": "Owner"}),
            )
            assert ok.status_code == 200
            assert len(ok.json()["submissions"]) == 1
        finally:
            (APPS_DIR / "shop" / "app.json").write_text(backup, encoding="utf-8")


# ---------------------------------------------------------------- app assets


class TestApps:
    def test_twelve_apps_are_installed(self):
        assert len(available_apps()) == 12

    @pytest.mark.parametrize("slug", sorted(p.parent.name for p in APPS_DIR.glob("*/app.json")))
    def test_app_has_manifest_and_page(self, slug):
        manifest = json.loads((APPS_DIR / slug / "app.json").read_text(encoding="utf-8"))
        assert manifest["title"]
        assert manifest["summary"]
        assert isinstance(manifest.get("admin", []), list)

        html = (APPS_DIR / slug / "index.html").read_text(encoding="utf-8")
        assert "telegram-web-app.js" in html, "the Telegram SDK must be loaded"
        assert "/shared/tg.js" in html
        assert "/shared/app.css" in html
        assert "TG.requireTelegram" in html, "must degrade outside Telegram"
        assert html.count("<script") == html.count("</script>")

    @pytest.mark.parametrize("slug", sorted(p.parent.name for p in APPS_DIR.glob("*/app.json")))
    def test_app_never_trusts_the_client_for_identity(self, slug):
        """No app may read the user id out of initDataUnsafe and act on it."""
        html = (APPS_DIR / slug / "index.html").read_text(encoding="utf-8")
        assert "initDataUnsafe" not in html, f"{slug} reads unverified Telegram data"

    @pytest.mark.parametrize("slug", sorted(p.parent.name for p in APPS_DIR.glob("*/app.json")))
    def test_app_escapes_interpolated_values(self, slug):
        """Every app renders with innerHTML, so it must escape what it injects."""
        html = (APPS_DIR / slug / "index.html").read_text(encoding="utf-8")
        if "innerHTML" in html:
            assert "TG.escape" in html, f"{slug} builds HTML without escaping"

    def test_app_pages_are_served(self, client):
        for app in available_apps():
            response = client.get(f"/app/{app['slug']}/")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]

    def test_shared_assets_are_served(self, client):
        assert client.get("/shared/tg.js").status_code == 200
        assert client.get("/shared/app.css").status_code == 200

    def test_shared_path_traversal_never_leaks_a_file(self, client):
        """What matters is that nothing outside shared/ is ever returned.

        A bare `/shared/..` is collapsed to `/` by any HTTP client before it
        reaches us, so the meaningful cases are dotfiles and encoded escapes.
        """
        assert client.get("/shared/.env").status_code == 400

        for evil in [
            "%2e%2e%2fcore%2fauth.py",
            "%2e%2e%2f%2e%2e%2fREADME.md",
            "..%2Fcore%2Fstore.py",
        ]:
            response = client.get(f"/shared/{evil}")
            assert response.status_code in {400, 404}, evil
            assert "verify_init_data" not in response.text
            assert "class AppStore" not in response.text

    def test_index_lists_every_app(self, client):
        body = client.get("/").text
        for app in available_apps():
            assert app["title"] in body

    def test_healthz(self, client):
        body = client.get("/healthz").json()
        assert body["status"] == "ok"
        assert body["apps"] == 12
        assert body["auth"] == "configured"

    def test_health_reports_missing_token(self, store):
        client = TestClient(create_app(store=store, bot_token=""))
        assert client.get("/healthz").json()["auth"] == "BOT_TOKEN missing"

    def test_apps_catalogue_is_public(self, client):
        response = client.get("/api/apps")
        assert response.status_code == 200
        assert len(response.json()["apps"]) == 12
