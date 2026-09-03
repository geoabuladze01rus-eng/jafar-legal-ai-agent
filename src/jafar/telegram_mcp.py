from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from jafar.config import settings
from jafar.telegram_approval import TelegramApprovalRecord, TelegramApprovalStore
from jafar.telegram_errors import TelegramDeliveryUncertainError
from jafar.telegram_polls import TelegramPollStore, validate_poll
from jafar.telegram_publishing import (
    MAX_PHOTO_BYTES,
    TelegramPublisher,
    validate_filename,
    validate_photo_bytes,
    validate_photo_url,
    validate_video_bytes,
    validate_video_url,
)
from jafar.telegram_runtime import TelegramBotHttpClient
from jafar.telegram_scheduler import (
    ScheduledItem,
    TelegramScheduler,
    TelegramScheduleStore,
    parse_schedule_time,
)

_LOCAL_MCP_HOSTS = {"127.0.0.1", "localhost", "::1"}
_MCP_TOKEN_PLACEHOLDERS = {"replace-me", "changeme", "change-me", "secret"}
_MAX_MCP_REQUEST_BODY_BYTES = 15 * 1024 * 1024
_MCP_INSTRUCTIONS = (
    "JAFAR Telegram is approval-first. Create a draft, show its immutable summary to the "
    "owner, obtain an explicit human APPROVE decision, then execute the approval ID. Never "
    "approve, execute, alter a destination, or bypass a Telegram allowlist automatically. "
    "Delivery-uncertain records require manual reconciliation and must never be retried."
)


class _StaticTokenVerifier:
    """Private MCP bearer verifier; supplied tokens are never logged or returned."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._token):
            return None
        return AccessToken(
            token="redacted",
            client_id="jafar-private-mcp",
            scopes=["jafar:telegram"],
        )


def _transport() -> str:
    return os.getenv("JAFAR_MCP_TRANSPORT", "stdio").strip().lower()


def validate_mcp_transport_security(
    *, transport: str | None = None, host: str | None = None
) -> tuple[str, str] | None:
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
    if parsed.query or parsed.fragment:
        raise RuntimeError("JAFAR_MCP_PUBLIC_URL must not contain a query or fragment")
    return token, public_url


def _mcp_server() -> MCPServer:
    remote = validate_mcp_transport_security()
    if remote is None:
        return MCPServer("Jafar Telegram", instructions=_MCP_INSTRUCTIONS)
    token, public_url = remote
    auth = AuthSettings(
        issuer_url=public_url,
        resource_server_url=public_url,
        required_scopes=["jafar:telegram"],
    )
    return MCPServer(
        "Jafar Telegram",
        instructions=_MCP_INSTRUCTIONS,
        auth=auth,
        token_verifier=_StaticTokenVerifier(token),
    )


mcp = _mcp_server()


def _allowed_chat_ids() -> set[str]:
    return {
        part.strip()
        for part in settings.telegram_allowed_chat_ids.split(",")
        if part.strip()
    }


def _require_allowed_chat(chat_id: int | str) -> str:
    chat = str(chat_id).strip()
    allowed = _allowed_chat_ids()
    if not allowed:
        raise RuntimeError("TELEGRAM_ALLOWED_CHAT_IDS is empty; outbound access is disabled")
    if chat not in allowed:
        raise PermissionError("Telegram destination is not allowlisted")
    return chat


def _require_token() -> str:
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return token


def _live_send_enabled() -> bool:
    return bool(settings.telegram_production_send and not settings.telegram_dry_run)


def _require_live_send_token() -> str:
    if settings.telegram_dry_run:
        raise PermissionError("Telegram live publishing is disabled while TELEGRAM_DRY_RUN=true")
    if not settings.telegram_production_send:
        raise PermissionError("Telegram live publishing requires TELEGRAM_PRODUCTION_SEND=true")
    return _require_token()


def _require_owner_approver(approver: str, confirmation: str) -> str:
    value = approver.strip()
    if confirmation.strip().upper() != "APPROVE":
        raise PermissionError("explicit APPROVE confirmation is required")
    configured = (settings.telegram_owner_approver_id or "").strip()
    if settings.environment.strip().casefold() == "production" and not configured:
        raise RuntimeError("production Telegram approval requires TELEGRAM_OWNER_APPROVER_ID")
    if configured and not hmac.compare_digest(value, configured):
        raise PermissionError("Telegram approval identity does not match configured owner")
    if not value:
        raise ValueError("approver must not be empty")
    return value


def _decode_photo_base64(value: str) -> bytes:
    encoded = value.strip()
    if encoded.startswith("data:"):
        _, _, encoded = encoded.partition(",")
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("photo_base64 is not valid base64") from exc
    if not data:
        raise ValueError("photo_base64 decodes to an empty file")
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("photo exceeds 10 MB limit")
    return data


def _decode_video_base64(value: str) -> bytes:
    encoded = value.strip()
    if encoded.startswith("data:"):
        _, _, encoded = encoded.partition(",")
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("video_base64 is not valid base64") from exc
    if not data:
        raise ValueError("video_base64 decodes to an empty file")
    validate_video_bytes(data, max_bytes=settings.telegram_max_video_bytes)
    return data


def _store() -> TelegramScheduleStore:
    return TelegramScheduleStore(settings.telegram_scheduler_db_path)


def _approvals() -> TelegramApprovalStore:
    return TelegramApprovalStore(settings.telegram_scheduler_db_path)


def _polls() -> TelegramPollStore:
    return TelegramPollStore(
        settings.telegram_scheduler_db_path,
        identity_secret=settings.telegram_poll_identity_secret,
    )


def _publisher() -> TelegramPublisher:
    return TelegramPublisher(
        lambda: TelegramBotHttpClient(_require_live_send_token()),
        _require_allowed_chat,
    )


def _key(kind: str, chat: str, payload: dict[str, Any], scheduled: str) -> str:
    return "approved:" + hashlib.sha256(
        f"{kind}|{chat}|{scheduled}|{payload}".encode()
    ).hexdigest()


def _message_id(result: dict[str, Any], *, operation: str) -> int:
    value = result.get("message_id")
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"Telegram {operation} returned no valid message_id")
    return value


def _poll_id(result: dict[str, Any]) -> str:
    poll = result.get("poll")
    if not isinstance(poll, dict):
        raise RuntimeError("Telegram sendPoll returned no poll object")
    value = poll.get("id")
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("Telegram sendPoll returned no poll identifier")
    return value


def _approval_summary(record: TelegramApprovalRecord) -> dict[str, Any]:
    return {
        "approval_id": record.approval_id,
        "kind": record.kind,
        "chat_id": record.chat_id,
        "scheduled_for": record.scheduled_for,
        "payload_hash": record.payload_hash,
        "state": record.state,
        "approved_by": record.approved_by,
        "schedule_id": record.schedule_id,
        "message_id": record.message_id,
        "error": record.error,
        "has_photo": bool(
            record.payload.get("photo_url") or record.payload.get("photo_base64")
        ),
        "has_video": bool(
            record.payload.get("video_url") or record.payload.get("video_base64")
        ),
    }


def _scheduled(item: ScheduledItem) -> dict[str, Any]:
    return {
        "schedule_id": item.id,
        "kind": item.kind,
        "chat_id": item.chat_id,
        "scheduled_for": item.scheduled_for.isoformat(),
        "status": item.status,
        "recurrence_seconds": item.recurrence_seconds,
        "message_id": item.message_id,
        "error": item.error,
    }


async def _deliver(item: ScheduledItem) -> int | None:
    """Deliver an already-approved immutable scheduled payload."""
    if item.kind == "post":
        payload = item.payload
        image = (
            _decode_photo_base64(payload["photo_base64"])
            if payload.get("photo_base64")
            else None
        )
        video = (
            _decode_video_base64(str(payload["video_base64"]))
            if payload.get("video_base64")
            else None
        )
        result = await _publisher().publish(
            chat_id=item.chat_id,
            text=str(payload["text"]),
            photo_url=payload.get("photo_url"),
            photo_bytes=image,
            video_url=payload.get("video_url"),
            video_bytes=video,
            filename=str(payload.get("filename", "image.png")),
            max_video_bytes=settings.telegram_max_video_bytes,
        )
        return (
            result.message_ids[-1]
            if result.message_ids
            else result.photo_message_id or result.video_message_id
        )
    if item.kind == "poll":
        chat = _require_allowed_chat(item.chat_id)
        result = await TelegramBotHttpClient(_require_live_send_token()).send_poll(
            chat_id=chat,
            poll=item.payload,
        )
        message_id = _message_id(result, operation="sendPoll")
        returned_poll = result.get("poll")
        if not isinstance(returned_poll, dict):
            raise RuntimeError("Telegram sendPoll returned no poll object")
        _polls().record_sent(poll=returned_poll, chat_id=chat, message_id=message_id)
        return message_id
    raise ValueError("unsupported scheduled item kind")


async def _publish_immediately(record: TelegramApprovalRecord) -> int | None:
    if record.kind == "post":
        payload = record.payload
        image = (
            _decode_photo_base64(str(payload["photo_base64"]))
            if payload.get("photo_base64")
            else None
        )
        video = (
            _decode_video_base64(str(payload["video_base64"]))
            if payload.get("video_base64")
            else None
        )
        result = await _publisher().publish(
            chat_id=record.chat_id,
            text=str(payload["text"]),
            photo_url=payload.get("photo_url"),
            photo_bytes=image,
            video_url=payload.get("video_url"),
            video_bytes=video,
            filename=str(payload.get("filename", "image.png")),
            max_video_bytes=settings.telegram_max_video_bytes,
        )
        return (
            result.message_ids[-1]
            if result.message_ids
            else result.photo_message_id or result.video_message_id
        )
    if record.kind == "poll":
        chat = _require_allowed_chat(record.chat_id)
        result = await TelegramBotHttpClient(_require_live_send_token()).send_poll(
            chat_id=chat,
            poll=record.payload,
        )
        message_id = _message_id(result, operation="sendPoll")
        poll_id = _poll_id(result)
        returned_poll = result.get("poll")
        if not isinstance(returned_poll, dict) or str(returned_poll.get("id")) != poll_id:
            raise RuntimeError("Telegram poll identifier changed during validation")
        _polls().record_sent(poll=returned_poll, chat_id=chat, message_id=message_id)
        return message_id
    raise ValueError("approval kind is not directly publishable")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def telegram_status() -> dict[str, Any]:
    """Use this when checking Telegram readiness without exposing credentials or content."""
    return {
        "configured": bool((settings.telegram_bot_token or "").strip()),
        "allowed_chat_ids_count": len(_allowed_chat_ids()),
        "live_send_enabled": _live_send_enabled(),
        "scheduler_enabled": settings.telegram_scheduler_enabled,
        "remote_auth_configured": bool(settings.jafar_mcp_auth_token),
        "owner_approval_configured": bool(settings.telegram_owner_approver_id),
        "approval_required": True,
        "ollama_local_first": bool(settings.ollama_enabled),
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def telegram_create_post_draft(
    chat_id: int | str,
    text: str,
    scheduled_for: str | None = None,
    photo_url: str | None = None,
    photo_base64: str | None = None,
    video_url: str | None = None,
    video_base64: str | None = None,
    filename: str | None = None,
    recurrence_seconds: int | None = None,
    requested_by: str = "chatgpt",
) -> dict[str, Any]:
    """Use this when an owner asks to prepare a text/photo publication; it never publishes."""
    chat = _require_allowed_chat(chat_id)
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    has_photo_url = photo_url is not None
    has_photo_base64 = photo_base64 is not None
    has_video_url = video_url is not None
    has_video_base64 = video_base64 is not None
    if has_photo_url and has_photo_base64:
        raise ValueError("provide only one of photo_url or photo_base64")
    if has_video_url and has_video_base64:
        raise ValueError("provide only one of video_url or video_base64")
    if (has_photo_url or has_photo_base64) and (has_video_url or has_video_base64):
        raise ValueError("provide photo or video, not both")
    if has_photo_url:
        photo_url = validate_photo_url(photo_url)
    if has_photo_base64:
        validate_photo_bytes(_decode_photo_base64(photo_base64))
    if has_video_url:
        video_url = validate_video_url(video_url)
    if has_video_base64:
        _decode_video_base64(video_base64)
    filename = validate_filename(
        filename or ("video.mp4" if has_video_url or has_video_base64 else "image.png")
    )
    if (has_video_url or has_video_base64) and not filename.casefold().endswith(".mp4"):
        raise ValueError("video filename must end with .mp4")
    normalized_schedule = None
    if scheduled_for is not None:
        normalized_schedule = parse_schedule_time(scheduled_for).isoformat()
    if recurrence_seconds is not None and recurrence_seconds < 60:
        raise ValueError("recurrence_seconds must be at least 60")
    payload = {
        "text": text,
        "photo_url": photo_url,
        "photo_base64": photo_base64,
        "video_url": video_url,
        "video_base64": video_base64,
        "filename": filename,
        "recurrence_seconds": recurrence_seconds,
    }
    record = _approvals().create(
        kind="post",
        chat_id=chat,
        payload=payload,
        scheduled_for=normalized_schedule,
        requested_by=requested_by.strip() or "chatgpt",
    )
    return _approval_summary(record)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def telegram_create_poll_draft(
    chat_id: int | str,
    question: str,
    options: list[str],
    scheduled_for: str | None = None,
    is_anonymous: bool = True,
    allows_multiple_answers: bool = False,
    poll_type: str = "regular",
    correct_option_id: int | None = None,
    explanation: str | None = None,
    open_period: int | None = None,
    close_date: int | None = None,
    requested_by: str = "chatgpt",
) -> dict[str, Any]:
    """Use this when an owner asks to prepare a regular or quiz poll for approval."""
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
    normalized_schedule = None
    if scheduled_for is not None:
        normalized_schedule = parse_schedule_time(scheduled_for).isoformat()
    record = _approvals().create(
        kind="poll",
        chat_id=chat,
        payload=poll,
        scheduled_for=normalized_schedule,
        requested_by=requested_by.strip() or "chatgpt",
    )
    return _approval_summary(record)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def telegram_create_cancel_draft(
    schedule_id: str,
    requested_by: str = "chatgpt",
) -> dict[str, Any]:
    """Prepare cancellation of a pending scheduled item; cancellation itself requires approval."""
    item = _store().get(schedule_id.strip())
    if item.status != "pending":
        raise ValueError("only pending scheduled items can be cancelled")
    _require_allowed_chat(item.chat_id)
    record = _approvals().create(
        kind="cancel",
        chat_id=item.chat_id,
        payload={"schedule_id": item.id},
        scheduled_for=None,
        requested_by=requested_by.strip() or "chatgpt",
    )
    return _approval_summary(record)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def telegram_create_reschedule_draft(
    schedule_id: str,
    new_scheduled_for: str,
    requested_by: str = "chatgpt",
) -> dict[str, Any]:
    """Prepare a schedule-time change. The new exact time is bound into approval."""
    item = _store().get(schedule_id.strip())
    if item.status != "pending":
        raise ValueError("only pending scheduled items can be rescheduled")
    _require_allowed_chat(item.chat_id)
    normalized = parse_schedule_time(new_scheduled_for).isoformat()
    record = _approvals().create(
        kind="reschedule",
        chat_id=item.chat_id,
        payload={"schedule_id": item.id, "new_scheduled_for": normalized},
        scheduled_for=None,
        requested_by=requested_by.strip() or "chatgpt",
    )
    return _approval_summary(record)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def telegram_approve_publication(
    approval_id: str,
    approver: str,
    confirmation: str,
) -> dict[str, Any]:
    """Use this only after an owner explicitly confirms APPROVE for the immutable draft."""
    owner = _require_owner_approver(approver, confirmation)
    record = _approvals().approve(approval_id.strip(), approver=owner)
    return _approval_summary(record)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def telegram_execute_approved(approval_id: str) -> dict[str, Any]:
    """Execute exactly the previously approved action; replacement payloads are not accepted."""
    approvals = _approvals()
    record = approvals.get(approval_id.strip())
    if record.state != "approved":
        raise PermissionError("Telegram action is not in approved state")
    _require_allowed_chat(record.chat_id)

    if record.kind in {"post", "poll"} and record.scheduled_for is not None:
        if not settings.telegram_scheduler_enabled:
            raise PermissionError("Telegram scheduler is disabled")
    if not settings.telegram_dry_run and record.kind in {"post", "poll"}:
        # Refuse before consuming approval when production delivery is not explicitly live.
        _require_live_send_token()

    record = approvals.begin_execution(record.approval_id)

    try:
        if record.kind == "cancel":
            item = _store().cancel(str(record.payload["schedule_id"]))
            approvals.mark_published(record.approval_id, message_id=None)
            return {
                "ok": True,
                "approval_id": record.approval_id,
                "cancelled": _scheduled(item),
                "dry_run": settings.telegram_dry_run,
            }

        if record.kind == "reschedule":
            new_time = datetime.fromisoformat(str(record.payload["new_scheduled_for"]))
            item = _store().reschedule(str(record.payload["schedule_id"]), new_time)
            approvals.mark_published(record.approval_id, message_id=None)
            return {
                "ok": True,
                "approval_id": record.approval_id,
                "rescheduled": _scheduled(item),
                "dry_run": settings.telegram_dry_run,
            }

        if record.scheduled_for is not None:
            scheduled = datetime.fromisoformat(record.scheduled_for)
            recurrence_seconds = record.payload.get("recurrence_seconds") if record.kind == "post" else None
            payload = dict(record.payload)
            payload.pop("recurrence_seconds", None)
            item = _store().schedule(
                kind=record.kind,
                chat_id=record.chat_id,
                payload=payload,
                scheduled_for=scheduled,
                idempotency_key=_key(record.kind, record.chat_id, payload, record.scheduled_for),
                recurrence_seconds=recurrence_seconds,
            )
            approvals.mark_scheduled(record.approval_id, schedule_id=item.id)
            return {
                "ok": True,
                "approval_id": record.approval_id,
                "scheduled": _scheduled(item),
                "dry_run": settings.telegram_dry_run,
            }

        if settings.telegram_dry_run:
            completed = approvals.mark_dry_run_completed(record.approval_id)
            return {
                "ok": True,
                "approval_id": completed.approval_id,
                "state": completed.state,
                "dry_run": True,
            }

        message_id = await _publish_immediately(record)
    except TelegramDeliveryUncertainError:
        approvals.mark_delivery_uncertain(record.approval_id)
        raise
    except Exception as exc:
        approvals.mark_failed(record.approval_id, error=f"execution_{type(exc).__name__.casefold()}")
        raise
    approvals.mark_published(record.approval_id, message_id=message_id)
    return {
        "ok": True,
        "approval_id": record.approval_id,
        "state": "executed",
        "message_id": message_id,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def telegram_get_approval(approval_id: str) -> dict[str, Any]:
    """Return approval status without returning the post body or image bytes."""
    return _approval_summary(_approvals().get(approval_id.strip()))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def telegram_list_recent_approvals(limit: int = 20) -> dict[str, Any]:
    """List recent publication approval states without post bodies."""
    return {"items": [_approval_summary(item) for item in _approvals().list_recent(limit)]}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def telegram_list_scheduled_posts() -> dict[str, Any]:
    """List scheduled/failed/uncertain items without exposing post bodies or image bytes."""
    return {"items": [_scheduled(item) for item in _store().list()]}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def telegram_get_delivery_status(schedule_id: str) -> dict[str, Any]:
    """Return one persisted scheduler delivery state and Telegram message_id when known."""
    return _scheduled(_store().get(schedule_id.strip()))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def telegram_reconcile_delivery_uncertain(
    schedule_id: str,
    confirmed_executed: bool,
    message_id: int | None,
    approver: str,
    confirmation: str,
) -> dict[str, Any]:
    """Owner-only manual reconciliation. This never re-runs the Telegram send handler."""
    _require_owner_approver(approver, confirmation)
    item = _store().reconcile_uncertain(
        schedule_id.strip(),
        confirmed_executed=confirmed_executed,
        message_id=message_id,
    )
    return _scheduled(item)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def telegram_get_poll_results(poll_id: str) -> dict[str, Any]:
    """Read poll results only while the owning chat remains allowlisted."""
    result = _polls().results(poll_id.strip())
    chat_id = result.get("chat_id")
    if chat_id is None:
        raise PermissionError("poll is not bound to an allowlisted Telegram chat")
    _require_allowed_chat(chat_id)
    return result


async def run_scheduler_once() -> int:
    return await TelegramScheduler(
        _store(),
        _deliver,
        claim_timeout_seconds=settings.telegram_scheduler_claim_timeout_seconds,
    ).run_due()


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
        public_url = (settings.jafar_mcp_public_url or "").strip()
        public_host = urlparse(public_url).hostname
        if not public_host:
            raise RuntimeError("JAFAR_MCP_PUBLIC_URL has no hostname")

        transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                "127.0.0.1:*",
                "localhost:*",
                "[::1]:*",
                public_host,
                f"{public_host}:*",
            ],
            allowed_origins=[
                "http://127.0.0.1:*",
                "http://localhost:*",
                "http://[::1]:*",
                f"https://{public_host}",
                f"https://{public_host}:*",
            ],
        )

        mcp.run(
            transport="streamable-http",
            host=host,
            port=port,
            stateless_http=True,
            json_response=True,
            transport_security=transport_security,
            max_request_body_size=_MAX_MCP_REQUEST_BODY_BYTES,
        )
    elif selected_transport == "stdio":
        mcp.run()
    else:
        raise RuntimeError(f"unsupported JAFAR_MCP_TRANSPORT: {selected_transport or '<empty>'}")
