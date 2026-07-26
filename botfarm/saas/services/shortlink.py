"""Shortlink API — short URLs with click counting and expiry."""

from __future__ import annotations

import os
import re
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

SLUG_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alikes
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}


class ShortenRequest(BaseModel):
    url: str = Field(..., max_length=2048, description="The destination URL")
    slug: str = Field("", description="Custom slug; generated when empty")
    ttl_days: int = Field(0, ge=0, le=3650, description="0 means it never expires")


def _validate_target(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(400, "url must start with http:// or https://")
    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "url has no host")
    # Refuse to become an SSRF proxy into the host's own network.
    if host in BLOCKED_HOSTS or host.endswith(".internal") or host.startswith("169.254."):
        raise HTTPException(400, "That host is not allowed")
    if host.startswith(("10.", "192.168.")) or re.match(r"^172\.(1[6-9]|2\d|3[01])\.", host):
        raise HTTPException(400, "Private addresses are not allowed")
    return url.strip()


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/links")
    async def shorten(request: Request, body: ShortenRequest) -> dict:
        """Create a short link. Returns the public short URL."""
        key = await request.app.state.require_key(request)
        store = request.app.state.store
        target = _validate_target(body.url)

        if body.slug:
            if not SLUG_RE.match(body.slug):
                raise HTTPException(400, "slug must be 3-32 chars of A-Z, a-z, 0-9, _ or -")
            if not store.put_link(body.slug, target, key.id, body.ttl_days):
                raise HTTPException(409, f"Slug {body.slug!r} is already taken")
            slug = body.slug
        else:
            for _ in range(6):
                slug = "".join(secrets.choice(ALPHABET) for _ in range(7))
                if store.put_link(slug, target, key.id, body.ttl_days):
                    break
            else:  # pragma: no cover - astronomically unlikely
                raise HTTPException(500, "Could not allocate a slug, please retry")

        base = os.getenv("PUBLIC_BASE_URL", str(request.base_url)).rstrip("/")
        return {"slug": slug, "short_url": f"{base}/{slug}", "target": target}

    @router.get("/links/{slug}")
    async def stats(request: Request, slug: str) -> dict:
        """Click count and metadata for one link."""
        await request.app.state.require_key(request)
        data = request.app.state.store.link_stats(slug)
        if data is None:
            raise HTTPException(404, "No such link")
        return data

    return router


def build_public_router() -> APIRouter:
    """The redirect itself is unauthenticated — it is what visitors hit."""
    router = APIRouter()

    @router.get("/{slug}", include_in_schema=False)
    async def follow(request: Request, slug: str):
        if not SLUG_RE.match(slug):
            raise HTTPException(404, "Not found")
        target = request.app.state.store.resolve_link(slug)
        if target is None:
            raise HTTPException(404, "This link does not exist or has expired")
        return RedirectResponse(target, status_code=302)

    return router


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="shortlink",
        title="Shortlink API",
        tagline="Short URLs with click analytics and expiry — yours, on your domain.",
        summary="Create short links with custom slugs, TTL and click counting.",
        router=build_router(),
        endpoints=[
            ("POST /v1/links", "Create a short link"),
            ("GET /v1/links/{slug}", "Click count and metadata"),
            ("GET /{slug}", "Public redirect (no key needed)"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/links \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"url":"https://example.com/very/long/path","ttl_days":30}\''
        ),
    )
