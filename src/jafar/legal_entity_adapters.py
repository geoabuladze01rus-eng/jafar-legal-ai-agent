from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
import re
from typing import Any, Protocol
from urllib.parse import quote, urlparse

from .legal_entity_intelligence import EntityQuery


_SOURCE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")
_ALLOWED_STATUSES = {"found", "negative", "no_data", "error"}
_SAFE_ADAPTER_ERRORS = {
    "adapter_source_key_mismatch",
    "adapter_status_invalid",
    "adapter_data_must_be_object",
    "adapter_source_url_invalid",
}


@dataclass(slots=True)
class SourceResult:
    source_key: str
    status: str
    source_url: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None


class LegalEntitySource(Protocol):
    source_key: str

    def search(self, query: EntityQuery) -> SourceResult: ...


def validate_source_key(source_key: str) -> str:
    normalized = source_key.strip().casefold()
    if not _SOURCE_KEY_RE.fullmatch(normalized):
        raise ValueError("invalid_legal_entity_source_key")
    return normalized


def validate_public_url(url: str) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("public_source_url_must_be_http_or_https")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("public_source_url_credentials_forbidden")

    host = parsed.hostname.casefold()
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("public_source_url_localhost_forbidden")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise ValueError("public_source_url_private_address_forbidden")
    return value


def validate_public_search_template(template: str) -> str:
    value = template.strip()
    if value.count("{query}") != 1:
        raise ValueError("public_search_template_requires_single_query_placeholder")
    rendered = value.format(query="jafar-safe-probe")
    validate_public_url(rendered)
    return value


def _safe_adapter_error(exc: Exception) -> str:
    message = str(exc)
    if isinstance(exc, ValueError) and message in _SAFE_ADAPTER_ERRORS:
        return message
    return f"{type(exc).__name__}:source_lookup_failed"


def _validate_adapter_result(result: SourceResult, expected_source_key: str) -> SourceResult:
    if validate_source_key(result.source_key) != expected_source_key:
        raise ValueError("adapter_source_key_mismatch")
    status = result.status.strip().casefold()
    if status not in _ALLOWED_STATUSES:
        raise ValueError("adapter_status_invalid")
    if result.data is not None and not isinstance(result.data, dict):
        raise ValueError("adapter_data_must_be_object")
    if result.source_url is not None:
        try:
            validate_public_url(result.source_url)
        except ValueError as exc:
            raise ValueError("adapter_source_url_invalid") from exc
    return SourceResult(
        source_key=expected_source_key,
        status=status,
        source_url=result.source_url,
        data=result.data,
        error=result.error if status == "error" else None,
    )


class PublicSourceAdapter:
    """Safe adapter contract for a public source.

    Concrete adapters must use only documented/public endpoints and must not
    bypass authentication, CAPTCHA, robots controls, paywalls, or other access
    restrictions. Network transport is intentionally injected by the caller.
    """

    def __init__(self, source_key: str, source_url: str | None = None) -> None:
        self.source_key = validate_source_key(source_key)
        self.source_url = validate_public_url(source_url) if source_url else None

    def search(self, query: EntityQuery) -> SourceResult:
        return SourceResult(
            source_key=self.source_key,
            status="no_data",
            source_url=self.source_url,
            data={"query": query.value, "query_type": query.query_type},
        )


class PublicUrlSourceAdapter(PublicSourceAdapter):
    """Builds a deterministic public-search URL without performing network I/O."""

    def __init__(self, source_key: str, search_url_template: str) -> None:
        super().__init__(source_key)
        self.search_url_template = validate_public_search_template(search_url_template)

    def search(self, query: EntityQuery) -> SourceResult:
        url = self.search_url_template.format(query=quote(query.value, safe=""))
        return SourceResult(
            source_key=self.source_key,
            status="no_data",
            source_url=url,
            data={
                "query": query.value,
                "query_type": query.query_type,
                "transport": "not_configured",
            },
        )


class KadPublicAdapter(PublicUrlSourceAdapter):
    """KAD adapter boundary; transport remains injected and policy-controlled."""

    def __init__(self, search_url_template: str) -> None:
        super().__init__("kad", search_url_template)


class LegalEntitySourceRegistry:
    def __init__(self, adapters: list[LegalEntitySource] | None = None) -> None:
        self._adapters: dict[str, LegalEntitySource] = {}
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: LegalEntitySource) -> None:
        source_key = validate_source_key(adapter.source_key)
        if source_key in self._adapters:
            raise ValueError("duplicate_legal_entity_source_key")
        self._adapters[source_key] = adapter

    def keys(self) -> list[str]:
        return sorted(self._adapters)

    def search_all(self, query: EntityQuery) -> list[SourceResult]:
        results: list[SourceResult] = []
        for source_key, adapter in self._adapters.items():
            try:
                results.append(_validate_adapter_result(adapter.search(query), source_key))
            except Exception as exc:
                results.append(
                    SourceResult(
                        source_key=source_key,
                        status="error",
                        error=_safe_adapter_error(exc),
                    )
                )
        return results
