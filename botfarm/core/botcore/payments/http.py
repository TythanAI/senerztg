"""Shared aiohttp plumbing: one lazily-built session, retries, sane timeouts."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Mapping

import aiohttp

from .base import PaymentError

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=20, connect=8)
RETRY_STATUSES = {429, 500, 502, 503, 504}


class HttpClient:
    """Thin JSON client with bounded exponential backoff.

    Payment APIs fail transiently far more often than they fail for real; a
    bot that gives up on the first 502 silently loses sales.
    """

    def __init__(
        self,
        base_url: str = "",
        *,
        headers: Mapping[str, str] | None = None,
        timeout: aiohttp.ClientTimeout = DEFAULT_TIMEOUT,
        retries: int = 3,
        provider: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.retries = max(1, retries)
        self.provider = provider
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    self._session = aiohttp.ClientSession(
                        timeout=self.timeout, headers=self.headers
                    )
        return self._session

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        data: Any = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        expect_json: bool = True,
    ) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            try:
                session = await self.session()
                async with session.request(
                    method, url, json=json, data=data, params=params, headers=dict(headers or {})
                ) as resp:
                    text = await resp.text()
                    if resp.status in RETRY_STATUSES and attempt < self.retries:
                        raise _Transient(f"HTTP {resp.status}: {text[:200]}")
                    if resp.status >= 400:
                        raise PaymentError(
                            f"{self.provider or url}: HTTP {resp.status}: {text[:400]}",
                            provider=self.provider,
                            retryable=resp.status in RETRY_STATUSES,
                        )
                    if not expect_json:
                        return text
                    if not text:
                        return {}
                    try:
                        return await resp.json(content_type=None)
                    except Exception as exc:
                        raise PaymentError(
                            f"{self.provider}: response is not JSON: {text[:200]}",
                            provider=self.provider,
                        ) from exc
            except (_Transient, aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                delay = min(2 ** attempt, 8) + random.uniform(0, 0.4)
                log.warning(
                    "%s %s failed (attempt %s/%s): %s — retrying in %.1fs",
                    method,
                    url,
                    attempt,
                    self.retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise PaymentError(
            f"{self.provider or url}: request failed after {self.retries} attempts: {last_error}",
            provider=self.provider,
            retryable=True,
        )

    async def get(self, path: str, **kw: Any) -> Any:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, **kw: Any) -> Any:
        return await self.request("POST", path, **kw)

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None


class _Transient(Exception):
    """Internal marker for a retryable HTTP status."""
