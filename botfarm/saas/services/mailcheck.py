"""Email Validation API — syntax, domain, disposable and role-account checks.

No paid third-party lookups: syntax is RFC-shaped, the domain is resolved for
real, and the disposable list ships with the service.
"""

from __future__ import annotations

import asyncio
import re
import socket

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

# Deliberately pragmatic rather than fully RFC 5322 — the full grammar accepts
# addresses no mail provider will ever deliver to.
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)

DISPOSABLE = {
    "10minutemail.com", "guerrillamail.com", "mailinator.com", "tempmail.com",
    "temp-mail.org", "throwawaymail.com", "yopmail.com", "getnada.com",
    "sharklasers.com", "trashmail.com", "maildrop.cc", "dispostable.com",
    "fakeinbox.com", "mytemp.email", "moakt.com", "emailondeck.com",
    "tempinbox.com", "spamgourmet.com", "mailnesia.com", "tempr.email",
    "burnermail.io", "temp-mail.io", "1secmail.com", "mohmal.com",
}

ROLE_ACCOUNTS = {
    "admin", "administrator", "info", "support", "sales", "contact", "help",
    "billing", "abuse", "postmaster", "webmaster", "noreply", "no-reply",
    "office", "hello", "team", "marketing", "hr", "jobs", "careers", "security",
}

FREE_PROVIDERS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com",
    "icloud.com", "aol.com", "mail.ru", "yandex.ru", "proton.me", "protonmail.com",
    "gmx.de", "web.de", "zoho.com", "yandex.com", "bk.ru", "list.ru", "inbox.ru",
}

# Common typos → what the user almost certainly meant.
TYPOS = {
    "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gmail.co": "gmail.com",
    "gmail.con": "gmail.com", "hotmial.com": "hotmail.com", "yahooo.com": "yahoo.com",
    "outlok.com": "outlook.com", "yandex.ri": "yandex.ru", "mail.ri": "mail.ru",
}


class CheckRequest(BaseModel):
    email: str = Field(..., max_length=320)
    resolve_domain: bool = Field(True, description="Do a real DNS lookup on the domain")


class BatchRequest(BaseModel):
    emails: list[str] = Field(..., max_length=100)
    resolve_domain: bool = True


async def _domain_resolves(domain: str) -> bool:
    """True when the domain has any A/AAAA record. Never raises."""
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP), timeout=3.0
        )
        return True
    except (socket.gaierror, asyncio.TimeoutError, OSError):
        return False


async def _check(email: str, resolve: bool) -> dict:
    email = email.strip()
    normalised = email.lower()
    result: dict = {
        "email": email,
        "normalized": normalised,
        "valid_syntax": bool(EMAIL_RE.match(email)),
        "domain": "",
        "local_part": "",
        "disposable": False,
        "role_account": False,
        "free_provider": False,
        "domain_resolves": None,
        "suggestion": None,
        "score": 0,
    }

    if "@" not in normalised:
        return result

    local, _, domain = normalised.rpartition("@")
    result["local_part"] = local
    result["domain"] = domain
    result["disposable"] = domain in DISPOSABLE
    result["role_account"] = local.split("+")[0] in ROLE_ACCOUNTS
    result["free_provider"] = domain in FREE_PROVIDERS

    if domain in TYPOS:
        result["suggestion"] = f"{local}@{TYPOS[domain]}"

    if resolve and result["valid_syntax"]:
        result["domain_resolves"] = await _domain_resolves(domain)

    # 0-100 confidence that this address is worth sending to.
    score = 0
    if result["valid_syntax"]:
        score += 45
    if result["domain_resolves"]:
        score += 30
    elif result["domain_resolves"] is None and result["valid_syntax"]:
        score += 15
    if not result["disposable"]:
        score += 15
    if not result["role_account"]:
        score += 10
    result["score"] = min(100, score)
    result["deliverable"] = (
        result["valid_syntax"] and not result["disposable"] and result["domain_resolves"] is not False
    )
    return result


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/email/check")
    async def check(request: Request, body: CheckRequest) -> dict:
        """Validate one address and score how likely it is to be deliverable."""
        await request.app.state.require_key(request)
        return await _check(body.email, body.resolve_domain)

    @router.post("/email/batch")
    async def batch(request: Request, body: BatchRequest) -> dict:
        """Validate up to 100 addresses in one call."""
        await request.app.state.require_key(request)
        if not body.emails:
            raise HTTPException(400, "emails must not be empty")

        results = await asyncio.gather(
            *(_check(email, body.resolve_domain) for email in body.emails)
        )
        return {
            "count": len(results),
            "deliverable": sum(1 for r in results if r["deliverable"]),
            "disposable": sum(1 for r in results if r["disposable"]),
            "results": results,
        }

    @router.get("/email/disposable-domains")
    async def disposable(request: Request) -> dict:
        """The disposable-domain list this service checks against."""
        await request.app.state.require_key(request)
        return {"count": len(DISPOSABLE), "domains": sorted(DISPOSABLE)}

    return router


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="mailcheck",
        title="Email Validation API",
        tagline="Catch typos, throwaways and dead domains before they hit your list.",
        summary="Validate email syntax, resolve the domain, flag disposable and role accounts, suggest typo fixes.",
        router=build_router(),
        endpoints=[
            ("POST /v1/email/check", "Validate and score one address"),
            ("POST /v1/email/batch", "Validate up to 100 at once"),
            ("GET /v1/email/disposable-domains", "The blocklist in use"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/email/check \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"email":"user@gmial.com"}\''
        ),
    )
