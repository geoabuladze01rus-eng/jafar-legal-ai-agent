"""Local-only structured logging helpers with conservative redaction."""
from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

_SECRET = re.compile(
    r"(?i)(authorization|api[_-]?key|token|secret|password|jwt|cookie)"
    r"\s*(?:[:=]\s*(?:bearer\s+)?|\s+bearer\s+)[^\s,;]+"
)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def redact(value: Any) -> str:
    """Return a bounded, non-sensitive representation for local logs."""
    text = str(value)
    text = _SECRET.sub(r"\1=<redacted>", text)
    text = _EMAIL.sub("<email-redacted>", text)
    return text[:500]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": record.levelname,
            "component": record.name,
            "message": redact(record.getMessage()),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = redact(request_id)
        return json.dumps(payload, ensure_ascii=False)
