from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status_code: int
    text: str
    url: str


class PublicHttpClient(Protocol):
    def get(self, url: str, *, timeout: float = 10.0) -> HttpResponse: ...


@dataclass(frozen=True, slots=True)
class TransportPolicy:
    timeout_seconds: float = 10.0
    max_response_bytes: int = 2_000_000
    user_agent: str = "Jafar-Legal-AI-Agent/1.0"


class SafePublicSourceTransport:
    """Transport boundary for lawful public-source requests.

    The transport deliberately has no browser automation, CAPTCHA solving,
    credential handling, proxy rotation, or paywall bypass capabilities.
    """

    def __init__(self, client: PublicHttpClient, policy: TransportPolicy | None = None) -> None:
        self.client = client
        self.policy = policy or TransportPolicy()

    def get(self, url: str) -> HttpResponse:
        response = self.client.get(url, timeout=self.policy.timeout_seconds)
        if len(response.text.encode("utf-8")) > self.policy.max_response_bytes:
            raise ValueError("public source response exceeds configured size limit")
        if response.status_code >= 400:
            raise RuntimeError(f"public source returned HTTP {response.status_code}")
        return response


def result_from_response(source_key: str, response: HttpResponse) -> dict[str, Any]:
    return {
        "source_key": source_key,
        "status": "found",
        "source_url": response.url,
        "data": {"raw_text": response.text},
    }
