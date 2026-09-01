from __future__ import annotations


def safe_exception_label(exc: BaseException) -> str:
    """Return an operational error label without exception text or payload data."""

    name = type(exc).__name__
    return name if name.isidentifier() else "ApplicationError"
