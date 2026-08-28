from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from time import monotonic, sleep
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class HttpFetchResult:
    url: str
    status_code: int
    body: bytes
    content_type: str | None
    etag: str | None
    last_modified: str | None
    retrieved_at_monotonic: float

    @property
    def fingerprint(self) -> str:
        return sha256(self.body).hexdigest()


@dataclass(frozen=True, slots=True)
class HttpRetryPolicy:
    attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 4.0
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)


class Sleeper(Protocol):
    def __call__(self, seconds: float) -> None: ...


class HttpTransportError(RuntimeError):
    pass


class ResilientHttpTransport:
    """Minimal deterministic HTTP transport with bounded retries and source fingerprinting."""

    def __init__(
        self,
        *,
        retry: HttpRetryPolicy | None = None,
        timeout_seconds: float = 20.0,
        min_interval_seconds: float = 0.5,
        user_agent: str = "JafarLegalAI/0.1 (+case-law-source-adapter)",
        sleeper: Sleeper = sleep,
    ) -> None:
        self.retry = retry or HttpRetryPolicy()
        self.timeout_seconds = timeout_seconds
        self.min_interval_seconds = min_interval_seconds
        self.user_agent = user_agent
        self.sleeper = sleeper
        self._last_request_at: float | None = None

    def get(self, url: str) -> HttpFetchResult:
        self._respect_rate_limit()
        last_error: Exception | None = None
        for attempt in range(1, self.retry.attempts + 1):
            try:
                request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    body = response.read()
                    self._last_request_at = monotonic()
                    return HttpFetchResult(
                        url=response.geturl(),
                        status_code=int(getattr(response, "status", 200)),
                        body=body,
                        content_type=response.headers.get("Content-Type"),
                        etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified"),
                        retrieved_at_monotonic=self._last_request_at,
                    )
            except HTTPError as exc:
                last_error = exc
                self._last_request_at = monotonic()
                if exc.code not in self.retry.retry_statuses or attempt >= self.retry.attempts:
                    break
            except URLError as exc:
                last_error = exc
                self._last_request_at = monotonic()
                if attempt >= self.retry.attempts:
                    break
            self.sleeper(self._delay(attempt))
        raise HttpTransportError(f"GET failed for {url}: {last_error}")

    def _respect_rate_limit(self) -> None:
        if self._last_request_at is None or self.min_interval_seconds <= 0:
            return
        remaining = self.min_interval_seconds - (monotonic() - self._last_request_at)
        if remaining > 0:
            self.sleeper(remaining)

    def _delay(self, attempt: int) -> float:
        return min(self.retry.max_delay_seconds, self.retry.base_delay_seconds * (2 ** (attempt - 1)))
