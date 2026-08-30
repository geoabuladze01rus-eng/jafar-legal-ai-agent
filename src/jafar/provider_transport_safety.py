from __future__ import annotations

import ipaddress
import json
import os
import socket
from typing import Any, BinaryIO
from urllib.parse import urlsplit

DEFAULT_PROVIDER_HOSTS = frozenset(
    {
        "api.openai.com",
        "api.deepseek.com",
        "dashscope-us.aliyuncs.com",
        "dashscope-intl.aliyuncs.com",
        "generativelanguage.googleapis.com",
    }
)
DEFAULT_MAX_PROMPT_BYTES = 2_000_000
DEFAULT_MAX_RESPONSE_BYTES = 8_000_000


def trusted_provider_hosts() -> frozenset[str]:
    """Return reviewed provider hosts plus explicit deployment-specific additions.

    Custom hosts are opt-in because an arbitrary provider endpoint receives both confidential
    legal prompts and a provider credential. Keeping this allowlist at the transport boundary
    prevents a misconfigured environment variable from becoming a credential/prompt exfiltration
    path.
    """

    configured = {
        item.strip().casefold().rstrip(".")
        for item in os.getenv("AI_TRUSTED_PROVIDER_HOSTS", "").split(",")
        if item.strip()
    }
    return frozenset(DEFAULT_PROVIDER_HOSTS | configured)


def validate_provider_endpoint(url: str, *, allowed_hosts: frozenset[str] | None = None) -> str:
    if not isinstance(url, str) or not url.strip():
        raise RuntimeError("provider_endpoint_required")
    parsed = urlsplit(url.strip())
    if parsed.scheme.casefold() != "https":
        raise RuntimeError("provider_endpoint_https_required")
    if parsed.username is not None or parsed.password is not None:
        raise RuntimeError("provider_endpoint_userinfo_forbidden")
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if not hostname:
        raise RuntimeError("provider_endpoint_host_required")
    if hostname not in (allowed_hosts or trusted_provider_hosts()):
        raise RuntimeError("provider_endpoint_host_not_trusted")
    _reject_literal_private_address(hostname)
    return url.strip()


def validate_prompt_transport(prompt: str, *, max_bytes: int = DEFAULT_MAX_PROMPT_BYTES) -> None:
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("provider_prompt_required")
    if max_bytes <= 0:
        raise ValueError("provider_prompt_limit_invalid")
    if len(prompt.encode("utf-8")) > max_bytes:
        raise RuntimeError("provider_prompt_too_large")


def read_json_response_limited(
    response: BinaryIO,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    if max_bytes <= 0:
        raise ValueError("provider_response_limit_invalid")
    raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise RuntimeError("provider_response_too_large")
    try:
        decoded = raw.decode("utf-8")
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("provider_response_invalid_json") from exc
    if not isinstance(data, dict):
        raise RuntimeError("provider_response_must_be_object")  # noqa: TRY004
    return data


def _reject_literal_private_address(hostname: str) -> None:
    """Reject IP literals even if someone accidentally adds one to the trusted-host list."""

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise RuntimeError("provider_endpoint_private_address_forbidden")


def resolved_host_is_public(hostname: str) -> bool:
    """Best-effort helper for deployment diagnostics without performing network I/O in validation.

    Runtime endpoint policy is host-allowlist based. Operators may call this helper in diagnostics
    to detect DNS records resolving to non-global addresses without making endpoint validation
    dependent on DNS availability during process startup.
    """

    try:
        infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    addresses = {item[4][0] for item in infos}
    if not addresses:
        return False
    try:
        return all(ipaddress.ip_address(item).is_global for item in addresses)
    except ValueError:
        return False
