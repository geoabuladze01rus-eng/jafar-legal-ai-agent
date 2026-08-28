from __future__ import annotations

import json
import socket
import urllib.error


def classify_openai_failure(*, status: int | None = None, error: BaseException | None = None, response_shape_valid: bool | None = None) -> str:
    if status in {401, 403}: return "AUTHENTICATION"
    if status == 404: return "MODEL_UNAVAILABLE"
    if status == 429: return "RATE_LIMIT"
    if status is not None and status >= 500: return "PROVIDER_ERROR"
    if status in {400, 422}: return "INVALID_REQUEST"
    if response_shape_valid is False: return "INVALID_RESPONSE"
    if isinstance(error, TimeoutError): return "TIMEOUT"
    if isinstance(error, (urllib.error.URLError, socket.timeout, ConnectionError)): return "NETWORK"
    return "UNKNOWN"


def classify_http_error(status: int, body: bytes | None = None) -> str:
    """Classify an HTTP failure without exposing the provider response."""
    if status == 429 and body:
        try:
            code = str(json.loads(body.decode("utf-8")).get("error", {}).get("code", "")).lower()
        except (ValueError, UnicodeDecodeError, AttributeError):
            code = ""
        if "quota" in code or "billing" in code or "insufficient" in code:
            return "QUOTA_OR_BILLING"
    return classify_openai_failure(status=status)
