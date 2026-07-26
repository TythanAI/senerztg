"""Time Toolkit — timezone conversion, business days, humanised durations."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec


class ConvertRequest(BaseModel):
    datetime: str = Field(..., description="ISO-8601; naive values are read in `from_tz`")
    from_tz: str = Field("UTC", description="IANA zone, e.g. Europe/Moscow")
    to_tz: str = Field("UTC", description="IANA zone, e.g. America/New_York")


class BusinessDaysRequest(BaseModel):
    start: str = Field(..., description="ISO date")
    end: str = Field("", description="ISO date; omit when using `days`")
    days: int = Field(0, description="Add this many business days to `start` instead")
    holidays: list[str] = Field(default_factory=list, description="Extra ISO dates to skip")
    weekend: list[int] = Field(default_factory=lambda: [5, 6], description="0=Mon … 6=Sun")


class HumanizeRequest(BaseModel):
    seconds: float = Field(..., ge=0)
    language: str = Field("en", description="'en' or 'ru'")
    precision: int = Field(2, ge=1, le=6, description="How many units to include")


UNITS_EN = (("year", 31_536_000), ("month", 2_592_000), ("day", 86_400),
            ("hour", 3_600), ("minute", 60), ("second", 1))

UNITS_RU = (
    (("год", "года", "лет"), 31_536_000),
    (("месяц", "месяца", "месяцев"), 2_592_000),
    (("день", "дня", "дней"), 86_400),
    (("час", "часа", "часов"), 3_600),
    (("минута", "минуты", "минут"), 60),
    (("секунда", "секунды", "секунд"), 1),
)


def _plural_ru(number: int, forms: tuple[str, str, str]) -> str:
    """Russian needs three plural forms; getting this wrong reads as broken."""
    if 11 <= number % 100 <= 14:
        return forms[2]
    last = number % 10
    if last == 1:
        return forms[0]
    if 2 <= last <= 4:
        return forms[1]
    return forms[2]


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise HTTPException(400, f"Unknown timezone {name!r} — use an IANA name") from None


def _date(value: str, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, f"{field} must be an ISO date (YYYY-MM-DD)") from None


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/time/convert")
    async def convert(request: Request, body: ConvertRequest) -> dict:
        """Convert a timestamp between zones, reporting the real UTC offsets."""
        await request.app.state.require_key(request)
        source, target = _zone(body.from_tz), _zone(body.to_tz)

        try:
            parsed = dt.datetime.fromisoformat(body.datetime.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "datetime must be ISO-8601") from None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=source)
        converted = parsed.astimezone(target)

        return {
            "input": parsed.isoformat(),
            "from_tz": body.from_tz,
            "to_tz": body.to_tz,
            "converted": converted.isoformat(),
            "unix": int(converted.timestamp()),
            "utc": parsed.astimezone(dt.timezone.utc).isoformat(),
            "from_utc_offset": parsed.strftime("%z"),
            "to_utc_offset": converted.strftime("%z"),
            "is_dst": bool(converted.dst()),
            "weekday": converted.strftime("%A"),
        }

    @router.get("/time/zones")
    async def zones(request: Request, search: str = "") -> dict:
        """Search the IANA timezone database."""
        await request.app.state.require_key(request)
        names = sorted(available_timezones())
        if search:
            needle = search.lower()
            names = [n for n in names if needle in n.lower()]
        return {"count": len(names), "zones": names[:500]}

    @router.get("/time/now")
    async def now(request: Request, tz: str = "UTC") -> dict:
        """Current time in a zone, with the fields most callers want."""
        await request.app.state.require_key(request)
        current = dt.datetime.now(_zone(tz))
        iso_year, iso_week, iso_weekday = current.isocalendar()
        return {
            "timezone": tz,
            "iso": current.isoformat(),
            "unix": int(current.timestamp()),
            "date": current.date().isoformat(),
            "time": current.strftime("%H:%M:%S"),
            "weekday": current.strftime("%A"),
            "iso_week": iso_week,
            "iso_year": iso_year,
            "iso_weekday": iso_weekday,
            "day_of_year": current.timetuple().tm_yday,
            "utc_offset": current.strftime("%z"),
        }

    @router.post("/time/business-days")
    async def business_days(request: Request, body: BusinessDaysRequest) -> dict:
        """Count business days between dates, or add N business days to one."""
        await request.app.state.require_key(request)
        start = _date(body.start, "start")
        weekend = {d for d in body.weekend if 0 <= d <= 6}
        holidays = {_date(h, "holidays") for h in body.holidays}

        def is_working(day: dt.date) -> bool:
            return day.weekday() not in weekend and day not in holidays

        if body.days:
            step = 1 if body.days > 0 else -1
            remaining = abs(body.days)
            cursor = start
            guard = 0
            while remaining > 0 and guard < 100_000:
                guard += 1
                cursor += dt.timedelta(days=step)
                if is_working(cursor):
                    remaining -= 1
            return {
                "start": start.isoformat(),
                "business_days_added": body.days,
                "result": cursor.isoformat(),
                "weekday": cursor.strftime("%A"),
            }

        if not body.end:
            raise HTTPException(400, "Provide either `end` or a non-zero `days`")
        end = _date(body.end, "end")
        if end < start:
            start, end = end, start

        total = (end - start).days + 1
        working = sum(
            1 for offset in range(total) if is_working(start + dt.timedelta(days=offset))
        )
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "calendar_days": total,
            "business_days": working,
            "weekend_days": total - working - len([h for h in holidays if start <= h <= end
                                                   and h.weekday() not in weekend]),
            "holidays_counted": len([h for h in holidays if start <= h <= end]),
        }

    @router.post("/time/humanize")
    async def humanize(request: Request, body: HumanizeRequest) -> dict:
        """Turn a duration in seconds into readable text."""
        await request.app.state.require_key(request)
        remaining = int(body.seconds)

        if body.language == "ru":
            parts = []
            for forms, size in UNITS_RU:
                if len(parts) >= body.precision:
                    break
                count, remaining = divmod(remaining, size)
                if count:
                    parts.append(f"{count} {_plural_ru(count, forms)}")
            text = " ".join(parts) or "0 секунд"
        else:
            parts = []
            for name, size in UNITS_EN:
                if len(parts) >= body.precision:
                    break
                count, remaining = divmod(remaining, size)
                if count:
                    parts.append(f"{count} {name}{'s' if count != 1 else ''}")
            text = " ".join(parts) or "0 seconds"

        return {
            "seconds": body.seconds,
            "human": text,
            "iso_duration": _iso_duration(int(body.seconds)),
        }

    return router


def _iso_duration(seconds: int) -> str:
    days, rest = divmod(seconds, 86_400)
    hours, rest = divmod(rest, 3_600)
    minutes, secs = divmod(rest, 60)
    out = "P"
    if days:
        out += f"{days}D"
    if hours or minutes or secs:
        out += "T"
        if hours:
            out += f"{hours}H"
        if minutes:
            out += f"{minutes}M"
        if secs:
            out += f"{secs}S"
    return out if out not in {"P", "PT"} else "PT0S"


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="timekit",
        title="Time Toolkit API",
        tagline="Timezones, business days and readable durations — DST handled properly.",
        summary="Convert between IANA timezones, count or add business days with holidays, humanise durations.",
        router=build_router(),
        endpoints=[
            ("POST /v1/time/convert", "Convert between timezones"),
            ("GET /v1/time/now", "Current time in a zone"),
            ("GET /v1/time/zones", "Search the IANA zone database"),
            ("POST /v1/time/business-days", "Count or add working days"),
            ("POST /v1/time/humanize", "Seconds → readable text (en/ru)"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/time/business-days \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"start":"2026-01-05","days":10}\''
        ),
    )
