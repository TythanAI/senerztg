"""Geo Toolkit — distances, bounding boxes, geohashes and point-in-polygon."""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

EARTH_RADIUS_KM = 6371.0088
BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"  # geohash alphabet


class Point(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class DistanceRequest(BaseModel):
    from_: Point = Field(..., alias="from")
    to: Point
    unit: str = Field("km", description="km, mi or m")

    model_config = {"populate_by_name": True}


class BboxRequest(BaseModel):
    center: Point
    radius_km: float = Field(..., gt=0, le=20_000)


class GeohashRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    precision: int = Field(9, ge=1, le=12)


class PolygonRequest(BaseModel):
    point: Point
    polygon: list[Point] = Field(..., min_length=3, max_length=10_000)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass(bearing: float) -> str:
    points = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
    return points[round(bearing / 22.5) % 16]


def encode_geohash(lat: float, lon: float, precision: int) -> str:
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    out, bits, bit, even = [], 0, 0, True

    while len(out) < precision:
        if even:
            mid = sum(lon_range) / 2
            if lon > mid:
                bits |= 1 << (4 - bit)
                lon_range[0] = mid
            else:
                lon_range[1] = mid
        else:
            mid = sum(lat_range) / 2
            if lat > mid:
                bits |= 1 << (4 - bit)
                lat_range[0] = mid
            else:
                lat_range[1] = mid
        even = not even

        if bit < 4:
            bit += 1
        else:
            out.append(BASE32[bits])
            bits, bit = 0, 0

    return "".join(out)


def decode_geohash(geohash: str) -> tuple[float, float, float, float]:
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    even = True
    for char in geohash.lower():
        index = BASE32.find(char)
        if index < 0:
            raise HTTPException(400, f"{char!r} is not a geohash character")
        for mask in (16, 8, 4, 2, 1):
            target = lon_range if even else lat_range
            mid = sum(target) / 2
            if index & mask:
                target[0] = mid
            else:
                target[1] = mid
            even = not even
    return lat_range[0], lat_range[1], lon_range[0], lon_range[1]


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/geo/distance")
    async def distance(request: Request, body: DistanceRequest) -> dict:
        """Great-circle distance and initial bearing between two points."""
        await request.app.state.require_key(request)
        start, end = body.from_, body.to
        km = haversine_km(start.lat, start.lon, end.lat, end.lon)

        factors = {"km": 1.0, "mi": 0.621371, "m": 1000.0}
        if body.unit not in factors:
            raise HTTPException(400, "unit must be km, mi or m")

        bearing = bearing_deg(start.lat, start.lon, end.lat, end.lon)
        return {
            "distance": round(km * factors[body.unit], 4),
            "unit": body.unit,
            "distance_km": round(km, 4),
            "bearing_deg": round(bearing, 1),
            "compass": compass(bearing),
        }

    @router.post("/geo/bbox")
    async def bbox(request: Request, body: BboxRequest) -> dict:
        """Bounding box around a point — the WHERE clause for a radius search."""
        await request.app.state.require_key(request)
        lat, lon = body.center.lat, body.center.lon
        lat_delta = math.degrees(body.radius_km / EARTH_RADIUS_KM)

        # Longitude degrees shrink toward the poles; guard the cosine at ±90°.
        cos_lat = math.cos(math.radians(lat))
        if abs(cos_lat) < 1e-9:
            lon_delta = 180.0
        else:
            lon_delta = math.degrees(body.radius_km / (EARTH_RADIUS_KM * cos_lat))
            lon_delta = min(lon_delta, 180.0)

        return {
            "min_lat": round(max(-90.0, lat - lat_delta), 6),
            "max_lat": round(min(90.0, lat + lat_delta), 6),
            "min_lon": round(max(-180.0, lon - lon_delta), 6),
            "max_lon": round(min(180.0, lon + lon_delta), 6),
            "radius_km": body.radius_km,
            "note": "A bbox over-selects near the corners; filter with /geo/distance after.",
        }

    @router.post("/geo/geohash")
    async def geohash(request: Request, body: GeohashRequest) -> dict:
        """Encode coordinates to a geohash and report the cell it covers."""
        await request.app.state.require_key(request)
        code = encode_geohash(body.lat, body.lon, body.precision)
        min_lat, max_lat, min_lon, max_lon = decode_geohash(code)
        height = haversine_km(min_lat, min_lon, max_lat, min_lon)
        width = haversine_km(min_lat, min_lon, min_lat, max_lon)
        return {
            "geohash": code,
            "precision": body.precision,
            "bounds": {
                "min_lat": round(min_lat, 6), "max_lat": round(max_lat, 6),
                "min_lon": round(min_lon, 6), "max_lon": round(max_lon, 6),
            },
            "cell_size_km": {"width": round(width, 4), "height": round(height, 4)},
            "prefixes": [code[:i] for i in range(1, len(code) + 1)],
        }

    @router.get("/geo/geohash/{code}")
    async def geohash_decode(request: Request, code: str) -> dict:
        """Decode a geohash back to a centre point and bounds."""
        await request.app.state.require_key(request)
        if not 1 <= len(code) <= 12:
            raise HTTPException(400, "A geohash is 1-12 characters")
        min_lat, max_lat, min_lon, max_lon = decode_geohash(code)
        return {
            "geohash": code.lower(),
            "center": {"lat": round((min_lat + max_lat) / 2, 6),
                       "lon": round((min_lon + max_lon) / 2, 6)},
            "bounds": {
                "min_lat": round(min_lat, 6), "max_lat": round(max_lat, 6),
                "min_lon": round(min_lon, 6), "max_lon": round(max_lon, 6),
            },
        }

    @router.post("/geo/contains")
    async def contains(request: Request, body: PolygonRequest) -> dict:
        """Point-in-polygon by ray casting — delivery zones, geofences."""
        await request.app.state.require_key(request)
        x, y = body.point.lon, body.point.lat
        vertices = [(p.lon, p.lat) for p in body.polygon]

        inside = False
        count = len(vertices)
        j = count - 1
        for i in range(count):
            xi, yi = vertices[i]
            xj, yj = vertices[j]
            if (yi > y) != (yj > y):
                # Guard the horizontal-edge division.
                if abs(yj - yi) > 1e-12 and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                    inside = not inside
            j = i

        perimeter = sum(
            haversine_km(vertices[i][1], vertices[i][0],
                         vertices[(i + 1) % count][1], vertices[(i + 1) % count][0])
            for i in range(count)
        )
        return {"contains": inside, "vertices": count, "perimeter_km": round(perimeter, 3)}

    return router


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="geokit",
        title="Geo Toolkit API",
        tagline="Distances, radius boxes, geohashes and geofences — no map provider needed.",
        summary="Great-circle distance, bearing, bounding boxes, geohash encode/decode and point-in-polygon.",
        router=build_router(),
        endpoints=[
            ("POST /v1/geo/distance", "Distance and bearing between points"),
            ("POST /v1/geo/bbox", "Bounding box for a radius query"),
            ("POST /v1/geo/geohash", "Encode coordinates to a geohash"),
            ("GET /v1/geo/geohash/{code}", "Decode a geohash"),
            ("POST /v1/geo/contains", "Point-in-polygon geofence test"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/geo/distance \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"from":{"lat":55.75,"lon":37.62},"to":{"lat":59.94,"lon":30.31}}\''
        ),
    )
