"""QR Studio — QR codes as PNG or SVG, with colours and a centre logo."""

from __future__ import annotations

import base64
import io

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q

from saascore.app import ServiceSpec

LEVELS = {"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M, "Q": ERROR_CORRECT_Q, "H": ERROR_CORRECT_H}
MAX_PAYLOAD = 2953  # what a version-40 QR can hold


class QrRequest(BaseModel):
    data: str = Field(..., min_length=1, max_length=MAX_PAYLOAD, description="Text or URL to encode")
    size: int = Field(512, ge=64, le=2048, description="Output width in pixels")
    margin: int = Field(2, ge=0, le=16, description="Quiet zone, in modules")
    fill: str = Field("#000000", description="Foreground colour")
    background: str = Field("#FFFFFF", description="Background colour")
    level: str = Field("M", description="Error correction: L, M, Q or H")
    format: str = Field("png", description="png or svg")
    logo_url: str = Field("", description="Optional logo to embed in the centre")


def _colour(value: str) -> str:
    value = value.strip()
    if not value.startswith("#") or len(value) not in (4, 7):
        raise HTTPException(400, f"Colour must be #rgb or #rrggbb, got {value!r}")
    try:
        int(value[1:], 16)
    except ValueError:
        raise HTTPException(400, f"{value!r} is not a valid hex colour") from None
    return value


def build_router(spec_name: str = "qr") -> APIRouter:
    router = APIRouter()

    @router.post("/qr", responses={200: {"content": {"image/png": {}, "image/svg+xml": {}}}})
    async def make_qr(request: Request, body: QrRequest):
        """Render a QR code. Returns the image bytes directly."""
        await request.app.state.require_key(request)

        level = LEVELS.get(body.level.upper())
        if level is None:
            raise HTTPException(400, "level must be one of L, M, Q, H")

        fill, back = _colour(body.fill), _colour(body.background)

        if body.format.lower() == "svg":
            image = qrcode.make(
                body.data,
                image_factory=qrcode.image.svg.SvgPathImage,
                box_size=10,
                border=body.margin,
            )
            buffer = io.BytesIO()
            image.save(buffer)
            return Response(buffer.getvalue(), media_type="image/svg+xml")

        if body.format.lower() != "png":
            raise HTTPException(400, "format must be 'png' or 'svg'")

        # A logo covers the centre, so force high redundancy when one is used.
        qr = qrcode.QRCode(
            error_correction=ERROR_CORRECT_H if body.logo_url else level,
            box_size=10,
            border=body.margin,
        )
        qr.add_data(body.data)
        qr.make(fit=True)
        image = qr.make_image(fill_color=fill, back_color=back).convert("RGB")
        image = image.resize((body.size, body.size), Image.NEAREST)

        if body.logo_url:
            image = await _paste_logo(image, body.logo_url, back)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return Response(
            buffer.getvalue(),
            media_type="image/png",
            headers={"Content-Disposition": 'inline; filename="qr.png"'},
        )

    @router.post("/qr/base64")
    async def make_qr_base64(request: Request, body: QrRequest) -> dict:
        """Same as /qr but returns a data URI — handy for embedding in HTML."""
        response = await make_qr(request, body)
        mime = response.media_type or "image/png"
        encoded = base64.b64encode(response.body).decode()
        return {"mime": mime, "data_uri": f"data:{mime};base64,{encoded}", "bytes": len(response.body)}

    return router


async def _paste_logo(image: Image.Image, url: str, background: str) -> Image.Image:
    import httpx

    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "logo_url must be an http(s) URL")
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            if len(response.content) > 4_000_000:
                raise HTTPException(400, "Logo is larger than 4 MB")
            logo = Image.open(io.BytesIO(response.content)).convert("RGBA")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Could not fetch the logo: {exc}") from exc

    side = image.size[0] // 4
    logo.thumbnail((side, side), Image.LANCZOS)

    # White plate behind the logo keeps the code scannable.
    plate = Image.new("RGB", (logo.size[0] + 16, logo.size[1] + 16), background)
    position = ((image.size[0] - plate.size[0]) // 2, (image.size[1] - plate.size[1]) // 2)
    image.paste(plate, position)
    image.paste(logo, (position[0] + 8, position[1] + 8), logo)
    return image


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="qr",
        title="QR Studio API",
        tagline="Branded QR codes on demand — PNG or SVG, colours, logo in the middle.",
        summary="Generate QR codes with custom colours, quiet zone, error correction and an embedded logo.",
        router=build_router(),
        endpoints=[
            ("POST /v1/qr", "Render a QR code as PNG or SVG"),
            ("POST /v1/qr/base64", "Same, returned as a data URI"),
            ("GET /v1/usage", "Your quota for this month"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/qr \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -H "Content-Type: application/json" \\\n'
            '  -d \'{"data":"https://example.com","size":600,"fill":"#0B5FFF"}\' \\\n'
            "  --output qr.png"
        ),
    )
