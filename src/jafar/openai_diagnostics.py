from __future__ import annotations

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
