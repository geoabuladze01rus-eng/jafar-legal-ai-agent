from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any
from urllib.parse import urlparse

from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings

from jafar.config import settings
from jafar.telegram_polls import TelegramPollStore, validate_poll
from jafar.telegram_publishing import MAX_PHOTO_BYTES, TelegramPublisher, validate_photo_bytes
from jafar.telegram_runtime import TelegramBotHttpClient
from jafar.telegram_scheduler import (
    ScheduledItem,
    TelegramScheduler,
    TelegramScheduleStore,
    parse_schedule_time,
)


_LOCAL_MCP_HOSTS = {"127.0.0.1", "localhost", "::1"}
_MCP_TOKEN_PLACEHOLDERS = {"replace-me", "changeme", "change-me", "secret"}


class _StaticTokenVerifier:
    """MVP bearer protection for a private MCP endpoint; never log supplied tokens."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._token):
            return None
        return AccessToken(
            token="redacted", client_id="jafar-private-mcp", scopes=["jafar:telegram"]
        )


def _transport() -> str:
    return os.getenv("JAFAR_MCP_TRANSPORT", "stdio").strip().lower()


def validate_mcp_transport_security(
    *, transport: str | None = None, host: str | None = None
) -> tuple[str, str] | None:
    """Validate remote MCP before a socket is opened.

    Stdio is local-process IPC and does not need HTTP bearer auth. Streamable HTTP is intended
    only behind a local HTTPS reverse proxy/tunnel, so it must always use a strong bearer token,
    an HTTPS public URL, and a loopback bind. This prevents a common unsafe configuration where a
    loopback MCP endpoint is tunneled publicly but accidentally left unauthenticated.
    """

    selected = (transport or _transport()).strip().lower()
    if selected == "stdio":
        return None
    if selected != "streamable-http":
        raise RuntimeError(f"unsupported JAFAR_MCP_TRANSPORT: {selected or '<empty>'}")

    bind_host = (host or os.getenv("JAFAR_MCP_HOST", "127.0.0.1")).strip().lower()
    if bind_host not in _LOCAL_MCP_HOSTS:
        raise RuntimeError(
            "streamable HTTP MCP must bind to loopback and be exposed only through an authenticated HTTPS proxy/tunnel"
        )

    token = (settings.jafar_mcp_auth_token or "").strip()
    if len(token) < 32 or token.casefold() in _MCP_TOKEN_PLACEHOLDERS:
        raise RuntimeError(
            "streamable HTTP MCP requires a non-placeholder JAFAR_MCP_AUTH_TOKEN of at least 32 characters"
        )

    public_url = (settings.jafar_mcp_public_url or "").strip()
    parsed = urlparse(public_url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise RuntimeError("streamable HTTP MCP requires an HTTPS JAFAR_MCP_PUBLIC_URL")
    if parsed.username or parsed.password:
        raise RuntimeError("JAFAR_MCP_PUBLIC_URL must not embed credentials")

    return token, public_url


def _mcp_server() -> MCPServer:
    remote = validate_mcp_transport_security()
    if remote is None:
        return MCPServer("Jafar Telegram")
    token, public_url = remote
    auth = AuthSettings(
        issuer_url=public_url,
        resource_server_url=public_url,
        required_scopes=["jafar:telegram"],
    )
    return MCPServer("Jafar Telegram", auth=auth, token_verifier=_StaticTokenVerifier(token))


mcp = _mcp_server()


def _allowed_chat_ids() -> set[str]:
    return {part.strip() for part in settings.telegram_allowed_chat_ids.split(",") if part.strip()}


def _require_token() -> str:
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return token


def _require_allowed_chat(chat_id: int | str) -> str:
    chat, allowed = str(chat_id).strip(), _allowed_chat_ids()
    if not allowed:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_IDS is empty; outbound access is disabled")
    if chat not in allowed:
        raise PermissionError(f"Telegram chat {chat} is not in the allowlist")
    return chat


def _decode_photo_base64(value: str) -> bytes:
    value = value.strip()
    if value.startswith("data:"):
        _, _, value = value.partition(",")
    try:
        data = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError("photo_base64 is not valid base64") from exc
    if not data:
        raise ValueError("photo_base64 decodes to an empty file")
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("photo exceeds 10 MB limit")
    return data


def _store() -> TelegramScheduleStore:
    return TelegramScheduleStore(settings.telegram_scheduler_db_path)


def _polls() -> TelegramPollStore:
    return TelegramPollStore(settings.telegram_scheduler_db_path)


def _publisher() -> TelegramPublisher:
    return TelegramPublisher(lambda: TelegramBotHttpClient(_require_token()), _require_allowed_chat)


def _key(
    kind: str, chat: str, payload: dict[str, Any], scheduled: str, supplied: str | None
) -> str:
    if supplied is not None:
        supplied = supplied.strip()
        if not 1 <= len(supplied) <= 200:
            raise ValueError("idempotency_key must contain 1 to 200 non-whitespace characters")
        return supplied
    return "auto:" + hashlib.sha256(f"{kind}|{chat}|{scheduled}|{payload}".encode()).hexdigest()


async def _deliver(item: ScheduledItem) -> int | None:
    """Delivery-time policy check is intentionally inside every branch."""
    if item.kind == "post":
        payload = item.payload
        image = (
            _decode_photo_base64(payload["photo_base64"]) if payload.get("photo_base64") else None
        )
        result = await _publisher().publish(
            chat_id=item.chat_id,
            text=payload["text"],
            photo_url=payload.get("photo_url"),
            photo_bytes=image,
            filename=payload.get("filename", "image.png"),
        )
        return result.message_ids[-1] if result.message_ids else result.photo_message_id
    if item.kind == "poll":
        chat = _require_allowed_chat(item.chat_id)
        result = await TelegramBotHttpClient(_require_token()).send_poll(
            chat_id=chat, poll=item.payload
        )
        if isinstance(result.get("poll"), dict):
            _polls().record_sent(
                poll=result["poll"], chat_id=chat, message_id=result.get("message_id")
            )
        return result.get("message_id")
    raise ValueError(f"unsupported scheduled item kind {item.kind}")


def _scheduled(item: ScheduledItem, detail: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schedule_id": item.id,
        "kind": item.kind,
        "chat_id": item.chat_id,
        "scheduled_for": item.scheduled_for.isoformat(),
        "status": item.status,
        "idempotency_key": item.idempotency_key,
        "recurrence_seconds": item.recurrence_seconds,
        "message_id": item.message_id,
        "error": item.error,
    }
    if detail:
        result["has_photo"] = bool(
            item.payload.get("photo_url") or item.payload.get("photo_base64")
        )
    return result


@mcp.tool()
async def telegram_status() -> dict[str, Any]:
    """Return Telegram MCP configuration status without secrets."""
    return {
        "configured": bool((settings.telegram_bot_token or "").strip()),
        "allowed_chat_ids_count": len(_allowed_chat_ids()),
        "outbound_enabled": bool(_allowed_chat_ids()),
        "scheduler_db": settings.telegram_scheduler_db_path,
        "remote_auth_configured": bool(settings.jafar_mcp_auth_token),
    }


@mcp.tool()
async def telegram_send_message(chat_id: int | str, text: str) -> dict[str, Any]:
    """Send an allowlisted text message, safely splitting content over 4096 chars."""
    result = await _publisher().publish(chat_id=chat_id, text=text)
    return {
        "ok": True,
        "chat_id": _require_allowed_chat(chat_id),
        "message_id": result.message_ids[-1] if result.message_ids else None,
        "message_ids": result.message_ids,
    }


@mcp.tool()
async def telegram_publish_post(
    chat_id: int | str,
    text: str,
    photo_url: str | None = None,
    photo_base64: str | None = None,
    filename: str = "image.png",
) -> dict[str, Any]:
    """Publish text or a photo. A long caption becomes photo then complete text messages."""
    if photo_url and photo_base64:
        raise ValueError("provide only one of photo_url or photo_base64")
    image = _decode_photo_base64(photo_base64) if photo_base64 else None
    if image:
        validate_photo_bytes(image)
    result = await _publisher().publish(
        chat_id=chat_id, text=text, photo_url=photo_url, photo_bytes=image, filename=filename
    )
    return {
        "ok": True,
        "chat_id": _require_allowed_chat(chat_id),
        "mode": result.mode,
        "photo_message_id": result.photo_message_id,
        "message_id": result.message_ids[-1] if result.message_ids else result.photo_message_id,
        "message_ids": result.message_ids,
    }


@mcp.tool()
async def telegram_schedule_post(
    chat_id: int | str,
    text: str,
    scheduled_for: str,
    photo_url: str | None = None,
    photo_base64: str | None = None,
    filename: str = "image.png",
    idempotency_key: str | None = None,
    recurrence_seconds: int | None = None,
) -> dict[str, Any]:
    """Persist an allowlisted text/photo publication for a future timezone-aware time."""
    chat = _require_allowed_chat(chat_id)
    if not text.strip():
        raise ValueError("text must not be empty")
    if photo_url and photo_base64:
        raise ValueError("provide only one of photo_url or photo_base64")
    if photo_base64:
        validate_photo_bytes(_decode_photo_base64(photo_base64))
    scheduled = parse_schedule_time(scheduled_for)
    payload = {
        "text": text,
        "photo_url": photo_url,
        "photo_base64": photo_base64,
        "filename": filename,
    }
    item = _store().schedule(
        kind="post",
        chat_id=chat,
        payload=payload,
        scheduled_for=scheduled,
        idempotency_key=_key("post", chat, payload, scheduled.isoformat(), idempotency_key),
        recurrence_seconds=recurrence_seconds,
    )
    return _scheduled(item)


@mcp.tool()
async def telegram_list_scheduled_posts() -> dict[str, Any]:
    """List pending, sending and failed scheduled posts/polls; image bytes are never returned."""
    return {"items": [_scheduled(item, False) for item in _store().list()]}


@mcp.tool()
async def telegram_cancel_scheduled_post(schedule_id: str) -> dict[str, Any]:
    """Cancel a pending scheduled post or poll."""
    return _scheduled(_store().cancel(schedule_id))


@mcp.tool()
async def telegram_send_poll(
    chat_id: int | str,
    question: str,
    options: list[str],
    is_anonymous: bool = True,
    allows_multiple_answers: bool = False,
    poll_type: str = "regular",
    correct_option_id: int | None = None,
    explanation: str | None = None,
    open_period: int | None = None,
    close_date: int | None = None,
) -> dict[str, Any]:
    """Create a regular or quiz poll in an allowlisted Telegram chat."""
    chat = _require_allowed_chat(chat_id)
    poll = validate_poll(
        question=question,
        options=options,
        is_anonymous=is_anonymous,
        allows_multiple_answers=allows_multiple_answers,
        poll_type=poll_type,
        correct_option_id=correct_option_id,
        explanation=explanation,
        open_period=open_period,
        close_date=close_date,
    )
    result = await TelegramBotHttpClient(_require_token()).send_poll(
        chat_id=_require_allowed_chat(chat), poll=poll
    )
    if not isinstance(result.get("poll"), dict) or not result["poll"].get("id"):
        raise RuntimeError("Telegram sendPoll returned no poll identifier")
    _polls().record_sent(poll=result["poll"], chat_id=chat, message_id=result.get("message_id"))
    return {
        "ok": True,
        "chat_id": chat,
        "message_id": result.get("message_id"),
        "poll_id": result["poll"]["id"],
    }


@mcp.tool()
async def telegram_schedule_poll(
    chat_id: int | str,
    question: str,
    options: list[str],
    scheduled_for: str,
    is_anonymous: bool = True,
    allows_multiple_answers: bool = False,
    poll_type: str = "regular",
    correct_option_id: int | None = None,
    explanation: str | None = None,
    open_period: int | None = None,
    close_date: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Persist a poll for one future delivery."""
    chat = _require_allowed_chat(chat_id)
    poll = validate_poll(
        question=question,
        options=options,
        is_anonymous=is_anonymous,
        allows_multiple_answers=allows_multiple_answers,
        poll_type=poll_type,
        correct_option_id=correct_option_id,
        explanation=explanation,
        open_period=open_period,
        close_date=close_date,
    )
    scheduled = parse_schedule_time(scheduled_for)
    item = _store().schedule(
        kind="poll",
        chat_id=chat,
        payload=poll,
        scheduled_for=scheduled,
        idempotency_key=_key("poll", chat, poll, scheduled.isoformat(), idempotency_key),
    )
    return _scheduled(item)


@mcp.tool()
async def telegram_get_poll_results(poll_id: str) -> dict[str, Any]:
    """Return persisted poll state and available non-anonymous answers."""
    return _polls().results(poll_id)


async def run_scheduler_once() -> int:
    return await TelegramScheduler(_store(), _deliver).run_due()


if __name__ == "__main__":
    selected_transport = _transport()
    if selected_transport == "streamable-http":
        host = os.getenv("JAFAR_MCP_HOST", "127.0.0.1").strip()
        validate_mcp_transport_security(transport=selected_transport, host=host)
        try:
            port = int(os.getenv("JAFAR_MCP_PORT", "8000"))
        except ValueError as exc:
            raise RuntimeError("JAFAR_MCP_PORT must be an integer") from exc
        if not 1 <= port <= 65535:
            raise RuntimeError("JAFAR_MCP_PORT must be between 1 and 65535")
        mcp.run(
            transport="streamable-http",
            host=host,
            port=port,
            stateless_http=True,
            json_response=True,
        )
    elif selected_transport == "stdio":
        mcp.run()
    else:
        raise RuntimeError(f"unsupported JAFAR_MCP_TRANSPORT: {selected_transport or '<empty>'}")
