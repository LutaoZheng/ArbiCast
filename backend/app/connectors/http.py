import asyncio
import random
import time
from collections import deque
from datetime import UTC, datetime

import httpx

from app.schemas.domain import ConnectorHealth, Platform, RecentRequest


class ConnectorHTTP:
    def __init__(self, platform: Platform, base_url: str, connect_timeout: float = 5, read_timeout: float = 15):
        self.platform = platform
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(connect=connect_timeout, read=read_timeout, write=10, pool=5),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={"Accept": "application/json", "User-Agent": "ArbiCast/0.2 research-only"},
        )
        self.state = ConnectorHealth(platform=platform)
        self.recent: deque[RecentRequest] = deque(maxlen=20)
        self._failures = 0

    async def get(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def request(self, method: str, path: str, attempts: int = 3, **kwargs) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(attempts):
            started = time.perf_counter()
            self.state.last_attempt = datetime.now(UTC)
            self.state.request_count += 1
            status = None
            try:
                response = await self.client.request(method, path, **kwargs)
                status = response.status_code
                latency = (time.perf_counter() - started) * 1000
                if status == 429:
                    self.state.rate_limit_count += 1
                    retry_after = float(response.headers.get("retry-after", 0) or 0)
                    raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)
                response.raise_for_status()
                self._failures = 0
                self.state.connected = True
                self.state.last_success = datetime.now(UTC)
                self.state.latency_ms = round(latency, 1)
                self.state.last_error = None
                self.state.backoff_seconds = 0
                self.recent.appendleft(RecentRequest(platform=self.platform, method=method, path=path, status=status, latency_ms=latency, timestamp=datetime.now(UTC)))
                return response
            except (httpx.HTTPError, TimeoutError) as exc:
                last_error = exc
                latency = (time.perf_counter() - started) * 1000
                self._failures += 1
                self.state.connected = False
                self.state.error_count += 1
                self.state.last_error = f"{type(exc).__name__}: {str(exc)[:240]}"
                base = min(30.0, 2 ** min(self._failures - 1, 5))
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                    base = max(base, float(exc.response.headers.get("retry-after", 10) or 10))
                delay = min(30.0, base + random.uniform(0, min(.5, base * .1)))
                self.state.backoff_seconds = round(delay, 2)
                self.recent.appendleft(RecentRequest(platform=self.platform, method=method, path=path, status=status, latency_ms=latency, timestamp=datetime.now(UTC), error=self.state.last_error))
                if attempt < attempts - 1:
                    await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error

    async def close(self) -> None:
        await self.client.aclose()
