"""One server hosting every Mini App.

Each app is a self-contained HTML file plus a JSON config. The server serves
them, verifies every API call against Telegram's signature, and keeps the
per-app data. Apps never talk to the database directly — they call `/api/*`
with their initData, and the server decides what that user may see.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .auth import AuthError, InitData, verify_init_data
from .store import AppStore

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
APPS_DIR = ROOT / "apps"
SHARED_DIR = ROOT / "shared"


def load_manifest(slug: str) -> dict[str, Any]:
    path = APPS_DIR / slug / "app.json"
    if not path.exists():
        raise HTTPException(404, f"No such app: {slug}")
    return json.loads(path.read_text(encoding="utf-8"))


def available_apps() -> list[dict[str, Any]]:
    apps = []
    for manifest in sorted(APPS_DIR.glob("*/app.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["slug"] = manifest.parent.name
        apps.append(data)
    return apps


def create_app(*, store: AppStore | None = None, bot_token: str | None = None) -> FastAPI:
    store = store or AppStore(os.getenv("MINIAPP_DB", str(ROOT / "data" / "miniapps.db")))
    token = bot_token if bot_token is not None else os.getenv("BOT_TOKEN", "")

    app = FastAPI(title="Telegram Mini Apps", version="1.0.0", docs_url="/api/docs")
    app.state.store = store
    app.state.bot_token = token
    app.state.started = time.time()

    async def require_user(
        request: Request,
        x_init_data: str = Header(default="", alias="X-Init-Data"),
    ) -> InitData:
        """Every API call proves who it is. No exceptions, no dev bypass."""
        try:
            return verify_init_data(x_init_data, request.app.state.bot_token)
        except AuthError as exc:
            log.warning("rejected Mini App request: %s", exc)
            raise HTTPException(401, str(exc)) from exc

    # ------------------------------------------------------------ static

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> str:
        rows = "".join(
            f'<li><a href="/app/{a["slug"]}/">{a["title"]}</a>'
            f'<span>{a.get("summary", "")}</span></li>'
            for a in available_apps()
        )
        return (
            "<!doctype html><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>Mini Apps</title>"
            "<style>body{font:16px/1.6 system-ui;max-width:720px;margin:0 auto;padding:2rem 1rem}"
            "li{margin:.6rem 0}span{display:block;opacity:.65;font-size:.9em}"
            "a{color:inherit}</style>"
            f"<h1>Telegram Mini Apps</h1><ol>{rows}</ol>"
        )

    @app.get("/app/{slug}/", response_class=HTMLResponse, include_in_schema=False)
    async def serve_app(slug: str):
        path = APPS_DIR / _safe(slug) / "index.html"
        if not path.exists():
            raise HTTPException(404, "No such app")
        # no-store: an app cached across a config change shows stale prices.
        return HTMLResponse(
            path.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/shared/{name}", include_in_schema=False)
    async def serve_shared(name: str):
        path = (SHARED_DIR / _safe(name)).resolve()
        # Name filtering catches the obvious cases; resolving and re-checking
        # containment is what actually guarantees nothing outside shared/ is
        # ever served, whatever encoding the request used.
        if not path.is_relative_to(SHARED_DIR.resolve()):
            raise HTTPException(404, "Not found")
        if not path.exists() or not path.is_file():
            raise HTTPException(404, "Not found")
        return FileResponse(path, headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "apps": len(available_apps()),
                "uptime_seconds": int(time.time() - app.state.started),
                "auth": "configured" if app.state.bot_token else "BOT_TOKEN missing",
            }
        )

    # --------------------------------------------------------------- api

    @app.get("/api/apps")
    async def list_apps() -> dict[str, Any]:
        """Public catalogue of installed apps."""
        return {"apps": available_apps()}

    @app.get("/api/{slug}/config")
    async def app_config(slug: str, auth: InitData = Depends(require_user)) -> dict[str, Any]:
        """Everything the front-end needs to render, for this specific user."""
        manifest = load_manifest(_safe(slug))
        profile = store.profile(slug, auth.user.id)
        return {
            "app": {k: v for k, v in manifest.items() if k != "admin"},
            "user": {
                "id": auth.user.id,
                "name": auth.user.display_name,
                "username": auth.user.username,
                "language": auth.user.language_code,
                "is_premium": auth.user.is_premium,
            },
            "profile": profile,
            "start_param": auth.start_param,
        }

    @app.post("/api/{slug}/state")
    async def save_state(
        slug: str, payload: dict[str, Any], auth: InitData = Depends(require_user)
    ) -> dict[str, Any]:
        """Persist this user's state for this app (cart, answers, progress)."""
        if len(json.dumps(payload)) > 64_000:
            raise HTTPException(413, "State payload is too large")
        store.save_state(_safe(slug), auth.user.id, payload)
        return {"saved": True}

    @app.get("/api/{slug}/state")
    async def read_state(slug: str, auth: InitData = Depends(require_user)) -> dict[str, Any]:
        return {"state": store.read_state(_safe(slug), auth.user.id)}

    @app.post("/api/{slug}/submit")
    async def submit(
        slug: str, payload: dict[str, Any], auth: InitData = Depends(require_user)
    ) -> dict[str, Any]:
        """Record an order, booking, answer set or review and notify the owner."""
        manifest = load_manifest(_safe(slug))
        kind = str(payload.get("kind") or manifest.get("submit_kind") or "submission")

        if store.recent_submissions(_safe(slug), auth.user.id, minutes=1) >= 5:
            raise HTTPException(429, "Too many submissions, please slow down")

        record_id = store.add_submission(
            app=_safe(slug),
            tg_id=auth.user.id,
            username=auth.user.username or auth.user.display_name,
            kind=kind,
            payload=payload,
        )
        log.info("miniapp %s: %s #%s from %s", slug, kind, record_id, auth.user.id)
        return {
            "id": record_id,
            "status": "received",
            "message": manifest.get("thanks", "Спасибо! Заявка принята."),
        }

    @app.get("/api/{slug}/submissions")
    async def submissions(
        slug: str, limit: int = 50, auth: InitData = Depends(require_user)
    ) -> dict[str, Any]:
        """Owner-only feed. Admin ids live in the app manifest."""
        manifest = load_manifest(_safe(slug))
        admins = {int(a) for a in manifest.get("admin", []) if str(a).lstrip("-").isdigit()}
        if auth.user.id not in admins:
            raise HTTPException(403, "This view is for the shop owner")
        return {"submissions": store.list_submissions(_safe(slug), min(limit, 200))}

    return app


def _safe(name: str) -> str:
    """Reject anything that could climb out of the apps directory."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "Bad name")
    return name
