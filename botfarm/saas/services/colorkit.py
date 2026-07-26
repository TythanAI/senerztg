"""Colour Toolkit — conversion, palettes and WCAG contrast checking."""

from __future__ import annotations

import colorsys

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

SCHEMES = ("complementary", "analogous", "triadic", "tetradic", "monochromatic", "shades")


class ConvertRequest(BaseModel):
    color: str = Field(..., description="#rrggbb, rgb(r,g,b) or hsl(h,s%,l%)")


class PaletteRequest(BaseModel):
    color: str
    scheme: str = Field("analogous", description=f"One of: {', '.join(SCHEMES)}")
    count: int = Field(5, ge=2, le=12)


class ContrastRequest(BaseModel):
    foreground: str
    background: str
    font_size: int = Field(16, ge=1, le=200, description="Used to pick the WCAG threshold")
    bold: bool = False


def parse_color(value: str) -> tuple[int, int, int]:
    text = value.strip().lower()

    if text.startswith("#"):
        body = text[1:]
        if len(body) == 3:
            body = "".join(c * 2 for c in body)
        if len(body) != 6:
            raise HTTPException(400, f"{value!r} is not #rgb or #rrggbb")
        try:
            return tuple(int(body[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            raise HTTPException(400, f"{value!r} is not valid hex") from None

    if text.startswith("rgb"):
        parts = text[text.find("(") + 1 : text.rfind(")")].split(",")
        if len(parts) < 3:
            raise HTTPException(400, "rgb() needs three components")
        try:
            rgb = tuple(max(0, min(255, int(float(p.strip())))) for p in parts[:3])
        except ValueError:
            raise HTTPException(400, f"Cannot parse {value!r}") from None
        return rgb  # type: ignore[return-value]

    if text.startswith("hsl"):
        parts = text[text.find("(") + 1 : text.rfind(")")].split(",")
        if len(parts) < 3:
            raise HTTPException(400, "hsl() needs three components")
        try:
            hue = float(parts[0].strip()) % 360 / 360
            sat = float(parts[1].strip().rstrip("%")) / 100
            light = float(parts[2].strip().rstrip("%")) / 100
        except ValueError:
            raise HTTPException(400, f"Cannot parse {value!r}") from None
        red, green, blue = colorsys.hls_to_rgb(hue, light, sat)
        return (round(red * 255), round(green * 255), round(blue * 255))

    raise HTTPException(400, f"Unrecognised colour format: {value!r}")


def to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG 2.1 relative luminance."""
    channels = []
    for value in rgb:
        srgb = value / 255
        channels.append(srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    lum_a, lum_b = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def describe(rgb: tuple[int, int, int]) -> dict:
    red, green, blue = (c / 255 for c in rgb)
    hue, light, sat = colorsys.rgb_to_hls(red, green, blue)
    _, sat_v, val = colorsys.rgb_to_hsv(red, green, blue)
    luminance = relative_luminance(rgb)
    return {
        "hex": to_hex(rgb),
        "rgb": {"r": rgb[0], "g": rgb[1], "b": rgb[2]},
        "rgb_css": f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})",
        "hsl": {"h": round(hue * 360, 1), "s": round(sat * 100, 1), "l": round(light * 100, 1)},
        "hsl_css": f"hsl({round(hue * 360)}, {round(sat * 100)}%, {round(light * 100)}%)",
        "hsv": {"h": round(hue * 360, 1), "s": round(sat_v * 100, 1), "v": round(val * 100, 1)},
        "luminance": round(luminance, 4),
        "is_dark": luminance < 0.179,  # the WCAG threshold for white-on-colour text
        "best_text_color": "#ffffff" if luminance < 0.179 else "#000000",
    }


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/color/convert")
    async def convert(request: Request, body: ConvertRequest) -> dict:
        """One colour, every notation, plus the readable text colour for it."""
        await request.app.state.require_key(request)
        return describe(parse_color(body.color))

    @router.post("/color/palette")
    async def palette(request: Request, body: PaletteRequest) -> dict:
        """Build a harmonious palette from a base colour."""
        await request.app.state.require_key(request)
        base = parse_color(body.color)
        red, green, blue = (c / 255 for c in base)
        hue, light, sat = colorsys.rgb_to_hls(red, green, blue)
        scheme = body.scheme.lower()

        if scheme == "complementary":
            hues = [hue, (hue + 0.5) % 1]
            variants = [(h, light, sat) for h in hues]
        elif scheme == "analogous":
            span = 1 / 12
            offset = -(body.count // 2)
            variants = [((hue + (offset + i) * span) % 1, light, sat) for i in range(body.count)]
        elif scheme == "triadic":
            variants = [((hue + i / 3) % 1, light, sat) for i in range(3)]
        elif scheme == "tetradic":
            variants = [((hue + i / 4) % 1, light, sat) for i in range(4)]
        elif scheme == "monochromatic":
            variants = [
                (hue, min(0.95, max(0.05, 0.15 + i * (0.7 / max(1, body.count - 1)))), sat)
                for i in range(body.count)
            ]
        elif scheme == "shades":
            variants = [
                (hue, light * (1 - i / max(1, body.count)), sat) for i in range(body.count)
            ]
        else:
            raise HTTPException(400, f"scheme must be one of: {', '.join(SCHEMES)}")

        colors = []
        for h, l, s in variants[: body.count]:
            r, g, b = colorsys.hls_to_rgb(h % 1, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
            colors.append(describe((round(r * 255), round(g * 255), round(b * 255))))

        return {"base": to_hex(base), "scheme": scheme, "count": len(colors), "colors": colors}

    @router.post("/color/contrast")
    async def contrast(request: Request, body: ContrastRequest) -> dict:
        """WCAG 2.1 contrast check — the one accessibility audits actually run."""
        await request.app.state.require_key(request)
        foreground = parse_color(body.foreground)
        background = parse_color(body.background)
        ratio = contrast_ratio(foreground, background)

        # "Large text" is 18pt+, or 14pt+ when bold (WCAG 1.4.3).
        large = body.font_size >= 24 or (body.bold and body.font_size >= 18.66)
        aa_threshold = 3.0 if large else 4.5
        aaa_threshold = 4.5 if large else 7.0

        return {
            "foreground": to_hex(foreground),
            "background": to_hex(background),
            "ratio": round(ratio, 2),
            "large_text": large,
            "passes_aa": ratio >= aa_threshold,
            "passes_aaa": ratio >= aaa_threshold,
            "passes_ui_components": ratio >= 3.0,
            "required_aa": aa_threshold,
            "required_aaa": aaa_threshold,
            "verdict": (
                "AAA" if ratio >= aaa_threshold
                else "AA" if ratio >= aa_threshold
                else "fail"
            ),
        }

    return router


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="colorkit",
        title="Colour Toolkit API",
        tagline="Convert, harmonise and prove your contrast passes WCAG.",
        summary="Colour conversion across hex/RGB/HSL/HSV, palette generation and WCAG 2.1 contrast checking.",
        router=build_router(),
        endpoints=[
            ("POST /v1/color/convert", "Every notation for one colour"),
            ("POST /v1/color/palette", "Complementary, analogous, triadic and more"),
            ("POST /v1/color/contrast", "WCAG AA/AAA contrast verdict"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/color/contrast \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"foreground":"#767676","background":"#ffffff"}\''
        ),
    )
