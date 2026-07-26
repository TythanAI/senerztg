"""OG Image API — social preview cards rendered server-side.

Every blog and SaaS needs 1200×630 preview cards. Doing it with a headless
browser costs 300 MB of RAM per worker; doing it with Pillow costs nothing.
"""

from __future__ import annotations

import io
import textwrap

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

THEMES = {
    "light": {"bg": (255, 255, 255), "fg": (17, 17, 17), "muted": (110, 110, 115)},
    "dark": {"bg": (14, 16, 22), "fg": (245, 245, 247), "muted": (150, 152, 160)},
    "indigo": {"bg": (36, 33, 92), "fg": (255, 255, 255), "muted": (185, 182, 230)},
    "forest": {"bg": (18, 46, 38), "fg": (240, 253, 244), "muted": (150, 200, 175)},
    "sunset": {"bg": (52, 20, 34), "fg": (255, 241, 235), "muted": (232, 160, 140)},
}


class OgRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)
    subtitle: str = Field("", max_length=220)
    badge: str = Field("", max_length=40, description="Small label above the title")
    theme: str = Field("dark", description=f"One of: {', '.join(THEMES)}")
    accent: str = Field("#5B8DEF", description="Accent bar colour, #rrggbb")
    width: int = Field(1200, ge=400, le=2400)
    height: int = Field(630, ge=200, le=1350)


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        raise HTTPException(400, "accent must be #rgb or #rrggbb")
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        raise HTTPException(400, "accent is not valid hex") from None


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Use a real TTF when the host has one; degrade rather than fail."""
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/og", responses={200: {"content": {"image/png": {}}}})
    async def render(request: Request, body: OgRequest):
        """Render an Open Graph card as PNG."""
        await request.app.state.require_key(request)

        theme = THEMES.get(body.theme.lower())
        if theme is None:
            raise HTTPException(400, f"theme must be one of: {', '.join(THEMES)}")
        accent = _rgb(body.accent)

        image = Image.new("RGB", (body.width, body.height), theme["bg"])
        draw = ImageDraw.Draw(image)

        scale = body.width / 1200
        pad = int(80 * scale)

        # Accent bar down the left edge.
        draw.rectangle([0, 0, int(14 * scale), body.height], fill=accent)

        cursor = pad
        if body.badge:
            badge_font = _font(int(26 * scale), bold=True)
            box = draw.textbbox((0, 0), body.badge.upper(), font=badge_font)
            width, height = box[2] - box[0], box[3] - box[1]
            draw.rounded_rectangle(
                [pad, cursor, pad + width + int(28 * scale), cursor + height + int(20 * scale)],
                radius=int(8 * scale),
                fill=accent,
            )
            draw.text(
                (pad + int(14 * scale), cursor + int(9 * scale)),
                body.badge.upper(),
                font=badge_font,
                fill=theme["bg"],
            )
            cursor += height + int(48 * scale)

        title_font = _font(int(64 * scale), bold=True)
        wrap_at = max(16, int(30 * (body.width / 1200) * (64 / max(1, 64))))
        for line in textwrap.wrap(body.title, width=wrap_at)[:4]:
            draw.text((pad, cursor), line, font=title_font, fill=theme["fg"])
            cursor += int(78 * scale)

        if body.subtitle:
            cursor += int(16 * scale)
            sub_font = _font(int(32 * scale))
            for line in textwrap.wrap(body.subtitle, width=int(wrap_at * 1.9))[:3]:
                draw.text((pad, cursor), line, font=sub_font, fill=theme["muted"])
                cursor += int(44 * scale)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return Response(
            buffer.getvalue(),
            media_type="image/png",
            headers={
                "Content-Disposition": 'inline; filename="og.png"',
                "Cache-Control": "public, max-age=86400",
            },
        )

    @router.get("/og/themes")
    async def themes(request: Request) -> dict:
        """List the available themes."""
        await request.app.state.require_key(request)
        return {"themes": list(THEMES), "default_size": [1200, 630]}

    return router


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="ogimage",
        title="OG Image API",
        tagline="Social preview cards without running a headless browser.",
        summary="Render Open Graph / Twitter card images from a title, subtitle and theme.",
        router=build_router(),
        endpoints=[
            ("POST /v1/og", "Render a 1200×630 preview card"),
            ("GET /v1/og/themes", "List available themes"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/og \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"title":"Ship faster","subtitle":"No browser required","theme":"indigo"}\' \\\n'
            "  --output og.png"
        ),
    )
