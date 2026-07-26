"""Image Toolkit — resize, convert, compress and watermark, by URL or upload."""

from __future__ import annotations

import io

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from saascore.app import ServiceSpec

MAX_BYTES = 12_000_000
MAX_PIXELS = 40_000_000  # guards against decompression-bomb uploads
FORMATS = {"png": "PNG", "jpeg": "JPEG", "jpg": "JPEG", "webp": "WEBP", "gif": "GIF"}
POSITIONS = ("center", "top-left", "top-right", "bottom-left", "bottom-right")


def _open(data: bytes) -> Image.Image:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"Image exceeds {MAX_BYTES // 1_000_000} MB")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise HTTPException(400, f"Not a readable image: {exc}") from exc
    if image.size[0] * image.size[1] > MAX_PIXELS:
        raise HTTPException(413, "Image has too many pixels")
    return image


def _encode(image: Image.Image, fmt: str, quality: int) -> tuple[bytes, str]:
    target = FORMATS.get(fmt.lower())
    if target is None:
        raise HTTPException(400, f"format must be one of: {', '.join(sorted(set(FORMATS)))}")
    if target == "JPEG" and image.mode in {"RGBA", "P", "LA"}:
        # JPEG has no alpha channel — flatten onto white instead of erroring.
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[-1])
        image = background

    buffer = io.BytesIO()
    params: dict = {"optimize": True}
    if target in {"JPEG", "WEBP"}:
        params["quality"] = quality
    image.save(buffer, format=target, **params)
    return buffer.getvalue(), f"image/{target.lower()}"


async def _load(request: Request, url: str, upload: UploadFile | None) -> bytes:
    if upload is not None:
        return await upload.read()
    if not url:
        raise HTTPException(400, "Provide either an uploaded file or ?url=")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "url must be http(s)")

    import httpx

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content
    except Exception as exc:
        raise HTTPException(400, f"Could not fetch the image: {exc}") from exc


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/image/resize", responses={200: {"content": {"image/*": {}}}})
    async def resize(
        request: Request,
        url: str = Query("", description="Source image URL"),
        width: int = Query(0, ge=0, le=8000),
        height: int = Query(0, ge=0, le=8000),
        fit: str = Query("contain", description="contain, cover or stretch"),
        format: str = Query("webp"),
        quality: int = Query(82, ge=1, le=100),
        file: UploadFile | None = File(None),
    ):
        """Resize an image. `contain` preserves aspect, `cover` crops to fill."""
        await request.app.state.require_key(request)
        image = _open(await _load(request, url, file))

        if not width and not height:
            raise HTTPException(400, "Set width, height, or both")

        original_w, original_h = image.size
        if fit == "stretch" and width and height:
            image = image.resize((width, height), Image.LANCZOS)
        elif fit == "cover" and width and height:
            ratio = max(width / original_w, height / original_h)
            image = image.resize(
                (max(1, round(original_w * ratio)), max(1, round(original_h * ratio))),
                Image.LANCZOS,
            )
            left = (image.size[0] - width) // 2
            top = (image.size[1] - height) // 2
            image = image.crop((left, top, left + width, top + height))
        else:
            target_w = width or round(original_w * (height / original_h))
            target_h = height or round(original_h * (width / original_w))
            image.thumbnail((max(1, target_w), max(1, target_h)), Image.LANCZOS)

        data, mime = _encode(image, format, quality)
        return Response(data, media_type=mime, headers={"X-Output-Size": str(len(data))})

    @router.post("/image/convert", responses={200: {"content": {"image/*": {}}}})
    async def convert(
        request: Request,
        url: str = Query(""),
        format: str = Query("webp"),
        quality: int = Query(82, ge=1, le=100),
        file: UploadFile | None = File(None),
    ):
        """Convert between PNG, JPEG, WebP and GIF."""
        await request.app.state.require_key(request)
        source = await _load(request, url, file)
        image = _open(source)
        data, mime = _encode(image, format, quality)
        saved = len(source) - len(data)
        return Response(
            data,
            media_type=mime,
            headers={"X-Output-Size": str(len(data)), "X-Bytes-Saved": str(saved)},
        )

    @router.post("/image/watermark", responses={200: {"content": {"image/*": {}}}})
    async def watermark(
        request: Request,
        text: str = Query(..., min_length=1, max_length=80),
        url: str = Query(""),
        position: str = Query("bottom-right"),
        opacity: float = Query(0.55, ge=0.05, le=1.0),
        format: str = Query("png"),
        file: UploadFile | None = File(None),
    ):
        """Stamp a text watermark onto an image."""
        await request.app.state.require_key(request)
        if position not in POSITIONS:
            raise HTTPException(400, f"position must be one of: {', '.join(POSITIONS)}")

        image = _open(await _load(request, url, file)).convert("RGBA")
        layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(layer)

        size = max(14, image.size[0] // 24)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
            )
        except OSError:
            font = ImageFont.load_default()

        box = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = box[2] - box[0], box[3] - box[1]
        margin = max(10, image.size[0] // 50)
        coords = {
            "center": ((image.size[0] - text_w) // 2, (image.size[1] - text_h) // 2),
            "top-left": (margin, margin),
            "top-right": (image.size[0] - text_w - margin, margin),
            "bottom-left": (margin, image.size[1] - text_h - margin * 2),
            "bottom-right": (image.size[0] - text_w - margin, image.size[1] - text_h - margin * 2),
        }[position]

        alpha = int(255 * opacity)
        draw.text((coords[0] + 2, coords[1] + 2), text, font=font, fill=(0, 0, 0, alpha // 2))
        draw.text(coords, text, font=font, fill=(255, 255, 255, alpha))

        merged = Image.alpha_composite(image, layer)
        data, mime = _encode(merged, format, 90)
        return Response(data, media_type=mime)

    @router.post("/image/info")
    async def info(
        request: Request, url: str = Query(""), file: UploadFile | None = File(None)
    ) -> dict:
        """Dimensions, format, transparency and dominant colour, without re-encoding."""
        await request.app.state.require_key(request)
        source = await _load(request, url, file)
        image = _open(source)

        thumb = image.convert("RGB").copy()
        thumb.thumbnail((64, 64))
        colours = thumb.getcolors(64 * 64) or []
        dominant = max(colours, key=lambda c: c[0])[1] if colours else (0, 0, 0)

        return {
            "width": image.size[0],
            "height": image.size[1],
            "format": image.format,
            "mode": image.mode,
            "has_alpha": image.mode in {"RGBA", "LA", "PA"},
            "bytes": len(source),
            "megapixels": round(image.size[0] * image.size[1] / 1_000_000, 2),
            "dominant_color": "#%02x%02x%02x" % dominant,
        }

    return router


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="imgtool",
        title="Image Toolkit API",
        tagline="Resize, convert, compress and watermark — one endpoint each.",
        summary="Image processing over HTTP: resize with contain/cover, format conversion, watermarking and metadata.",
        router=build_router(),
        endpoints=[
            ("POST /v1/image/resize", "Resize with contain, cover or stretch"),
            ("POST /v1/image/convert", "Convert between PNG/JPEG/WebP/GIF"),
            ("POST /v1/image/watermark", "Stamp a text watermark"),
            ("POST /v1/image/info", "Dimensions, format and dominant colour"),
        ],
        example=(
            'curl -X POST "https://api.example.com/v1/image/resize'
            '?url=https://example.com/a.jpg&width=800&fit=cover&format=webp" \\\n'
            '  -H "Authorization: Bearer sk_live_..." --output small.webp'
        ),
    )
