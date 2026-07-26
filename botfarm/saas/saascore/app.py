"""FastAPI factory shared by every service in the rack.

A service supplies a name, a description, a router and a price sheet. This
module supplies everything that makes it a *business*: key auth, per-minute
rate limiting, monthly quota, usage reporting, Stripe/CryptoBot upgrades, a
landing page and OpenAPI docs.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .billing import BillingRouter
from .store import PLANS, ApiKey, Store

ADMIN_TOKEN_ENV = "SAAS_ADMIN_TOKEN"


@dataclass(slots=True)
class ServiceSpec:
    """Everything that distinguishes one product in the rack from another."""

    name: str
    title: str
    summary: str
    router: APIRouter
    version: str = "1.0.0"
    tagline: str = ""
    endpoints: list[tuple[str, str]] = field(default_factory=list)
    example: str = ""
    #: Monthly price per plan, overriding the rack default.
    pricing: dict[str, int] = field(default_factory=dict)

    def price(self, plan: str) -> int:
        if plan in self.pricing:
            return self.pricing[plan]
        return PLANS.get(plan, {}).get("price_eur", 0)


class RateLimiter:
    """Sliding-window limiter, per key, in memory."""

    def __init__(self) -> None:
        self._hits: dict[int, deque[float]] = defaultdict(deque)

    def check(self, key_id: int, rpm: int) -> bool:
        now = time.monotonic()
        window = self._hits[key_id]
        cutoff = now - 60
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= rpm:
            return False
        window.append(now)
        return True

    def prune(self, max_keys: int = 10_000) -> None:
        if len(self._hits) <= max_keys:
            return
        cutoff = time.monotonic() - 120
        for key_id in [k for k, v in self._hits.items() if not v or v[-1] < cutoff]:
            self._hits.pop(key_id, None)


def create_app(spec: ServiceSpec, *, store: Store | None = None) -> FastAPI:
    store = store or Store(os.getenv("SAAS_DB", f"{spec.name}.db"))
    limiter = RateLimiter()

    app = FastAPI(
        title=spec.title,
        description=spec.summary,
        version=spec.version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.store = store
    app.state.spec = spec
    app.state.limiter = limiter
    app.state.started = time.time()

    async def require_key(request: Request) -> ApiKey:
        """Authenticate, rate-limit and meter one call.

        Reads the headers off the Request rather than declaring them as
        parameters, so handlers can `await require_key(request)` directly and
        it still works when used with `Depends`.
        """
        if getattr(request.state, "api_key", None) is not None:
            # Already authenticated on this request — never bill it twice.
            return request.state.api_key

        authorization = request.headers.get("authorization", "")
        raw = ""
        if authorization.lower().startswith("bearer "):
            raw = authorization[7:].strip()
        else:
            raw = request.headers.get("x-api-key", "").strip()

        if not raw:
            raise HTTPException(401, "Missing API key. Send Authorization: Bearer sk_live_…")

        key = store.get_key(raw)
        if key is None or not key.is_valid():
            raise HTTPException(401, "Invalid or revoked API key")
        if not key.allows(spec.name):
            raise HTTPException(403, f"This key is not valid for the {spec.name} service")

        if not limiter.check(key.id, key.rpm):
            raise HTTPException(
                429,
                f"Rate limit exceeded ({key.rpm} requests/minute on the {key.plan} plan)",
                headers={"Retry-After": "60"},
            )

        total = store.record_call(key.id, request.url.path)
        if total > key.quota:
            raise HTTPException(
                402,
                f"Monthly quota exhausted ({key.quota} calls on the {key.plan} plan). "
                f"Upgrade at /v1/billing/plans",
            )

        request.state.api_key = key
        request.state.usage_total = total
        return key

    app.state.require_key = require_key

    @app.middleware("http")
    async def usage_headers(request: Request, call_next):
        response = await call_next(request)
        key: ApiKey | None = getattr(request.state, "api_key", None)
        if key is not None:
            used = getattr(request.state, "usage_total", 0)
            response.headers["X-Plan"] = key.plan
            response.headers["X-Quota-Limit"] = str(key.quota)
            response.headers["X-Quota-Used"] = str(used)
            response.headers["X-Quota-Remaining"] = str(max(0, key.quota - used))
        return response

    # ------------------------------------------------------------ meta routes

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "service": spec.name,
                "version": spec.version,
                "uptime_seconds": int(time.time() - app.state.started),
            }
        )

    @app.get("/v1/usage", tags=["account"])
    async def usage(key: ApiKey = Depends(require_key)) -> dict[str, Any]:
        """How much of this month's quota the caller has spent."""
        data = store.usage(key.id)
        return {
            "plan": key.plan,
            "quota": key.quota,
            "used": data["total"],
            "remaining": max(0, key.quota - data["total"]),
            "rpm": key.rpm,
            "period": data["period"],
            "by_endpoint": data["by_endpoint"],
        }

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def landing() -> str:
        return _landing_html(spec)

    @app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
    async def robots() -> str:
        return "User-agent: *\nAllow: /\n"

    app.include_router(spec.router, prefix="/v1", tags=[spec.name])
    app.include_router(BillingRouter(store, spec).router, prefix="/v1/billing", tags=["billing"])
    app.include_router(_admin_router(store, spec), prefix="/admin", tags=["admin"])

    return app


def _admin_router(store: Store, spec: ServiceSpec) -> APIRouter:
    """Key management, guarded by SAAS_ADMIN_TOKEN."""
    router = APIRouter()

    def require_admin(x_admin_token: str = Header(default="")) -> None:
        expected = os.getenv(ADMIN_TOKEN_ENV, "")
        if not expected:
            raise HTTPException(503, f"{ADMIN_TOKEN_ENV} is not set on this server")
        # Constant-time comparison; an admin token is worth brute-forcing.
        import hmac

        if not hmac.compare_digest(x_admin_token, expected):
            raise HTTPException(403, "Bad admin token")

    @router.post("/keys", dependencies=[Depends(require_admin)])
    async def create_key(
        plan: str = "free", label: str = "", email: str = "", ttl_days: int = 0
    ) -> dict[str, Any]:
        """Issue a key. The plaintext is shown once and never stored."""
        try:
            raw, key = store.create_key(
                plan=plan, label=label, email=email, service=spec.name, ttl_days=ttl_days
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"api_key": raw, "id": key.id, "plan": key.plan, "quota": key.quota}

    @router.get("/keys", dependencies=[Depends(require_admin)])
    async def list_keys(limit: int = 100) -> list[dict[str, Any]]:
        return [
            {
                "id": k.id,
                "prefix": k.prefix,
                "label": k.label,
                "plan": k.plan,
                "active": k.active,
                "email": k.email,
                "used_this_month": store.usage(k.id)["total"],
            }
            for k in store.list_keys(limit)
        ]

    @router.post("/keys/{key_id}/plan", dependencies=[Depends(require_admin)])
    async def set_plan(key_id: int, plan: str) -> dict[str, Any]:
        try:
            ok = store.set_plan(key_id, plan)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if not ok:
            raise HTTPException(404, "No such key")
        return {"id": key_id, "plan": plan}

    @router.delete("/keys/{key_id}", dependencies=[Depends(require_admin)])
    async def revoke(key_id: int) -> dict[str, Any]:
        if not store.revoke(key_id):
            raise HTTPException(404, "No such key")
        return {"id": key_id, "active": False}

    return router


def _landing_html(spec: ServiceSpec) -> str:
    rows = "".join(
        f"<tr><td><code>{method}</code></td><td>{desc}</td></tr>"
        for method, desc in spec.endpoints
    )
    plans = "".join(
        f"<div class=plan><h3>{name.title()}</h3>"
        f"<p class=price>{'Free' if spec.price(name) == 0 else f'€{spec.price(name)}/mo'}</p>"
        f"<p>{cfg['quota']:,} calls/mo</p><p>{cfg['rpm']} req/min</p></div>"
        for name, cfg in PLANS.items()
    )
    return f"""<!doctype html>
<html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{spec.title} — API</title>
<style>
:root{{color-scheme:light dark}}
body{{font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif;max-width:820px;margin:0 auto;padding:2.5rem 1.25rem}}
h1{{margin:0 0 .25rem}} .tagline{{opacity:.7;margin-top:0}}
code{{background:rgba(127,127,127,.15);padding:.15em .4em;border-radius:4px;font-size:.9em}}
pre{{background:rgba(127,127,127,.12);padding:1rem;border-radius:8px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;margin:1rem 0}}
td,th{{text-align:left;padding:.5rem .4rem;border-bottom:1px solid rgba(127,127,127,.25)}}
.plans{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1rem;margin:1.5rem 0}}
.plan{{border:1px solid rgba(127,127,127,.3);border-radius:10px;padding:1rem;text-align:center}}
.plan h3{{margin:0 0 .3rem;font-size:1rem}} .price{{font-size:1.4rem;font-weight:600;margin:.2rem 0}}
.plan p{{margin:.2rem 0;font-size:.88rem;opacity:.8}}
a{{color:inherit}}
</style></head><body>
<h1>{spec.title}</h1>
<p class=tagline>{spec.tagline or spec.summary}</p>
<p><a href="/docs">Interactive docs</a> · <a href="/openapi.json">OpenAPI</a> · <a href="/healthz">Health</a></p>
<h2>Endpoints</h2>
<table><tr><th>Endpoint</th><th>What it does</th></tr>{rows}</table>
<h2>Quick start</h2>
<pre>{spec.example or f'curl -H "Authorization: Bearer sk_live_..." https://api.example.com/v1/...'}</pre>
<h2>Plans</h2>
<div class=plans>{plans}</div>
<p style="opacity:.6;font-size:.85rem">Every response carries
<code>X-Quota-Used</code> and <code>X-Quota-Remaining</code>.</p>
</body></html>"""


def run(spec_factory: Callable[[], ServiceSpec]) -> None:  # pragma: no cover - entry point
    import uvicorn

    app = create_app(spec_factory())
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
