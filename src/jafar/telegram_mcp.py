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
from jafar.model_router import ModelRequest, ModelRouter
from jafar.telegram_editorial import (
    DEFAULT_RUBRICS,
    EditorialStore,
    redact_transcript,
    safety_check,
)
from jafar.telegram_media import MediaStore, generate_post, redact_case
from jafar.telegram_polls import TelegramPollStore, validate_poll
from jafar.telegram_publishing import (
    MAX_PHOTO_BYTES,
    TelegramPublisher,
    validate_filename,
    validate_photo_bytes,
    validate_photo_url,
)
from jafar.telegram_runtime import TelegramBotHttpClient

_editorial_router: ModelRouter | None = None


def configure_editorial_model_router(router: ModelRouter) -> None:
    """Inject the application's central router; Telegram never creates an LLM client."""
    global _editorial_router
    _editorial_router = router
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


def _live_send_enabled() -> bool:
    return bool(settings.telegram_production_send and not settings.telegram_dry_run)


def _require_live_send_token() -> str:
    """Require the same explicit live-send gate used by the rest of Jafar's Telegram runtime."""

    if settings.telegram_dry_run:
        raise PermissionError("Telegram live publishing is disabled while TELEGRAM_DRY_RUN=true")
    if not settings.telegram_production_send:
        raise PermissionError("Telegram live publishing requires TELEGRAM_PRODUCTION_SEND=true")
    return _require_token()


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


def _editorial() -> EditorialStore:
    return EditorialStore(settings.telegram_scheduler_db_path)


def _media() -> MediaStore:
    return MediaStore(settings.telegram_scheduler_db_path)


def _publisher() -> TelegramPublisher:
    return TelegramPublisher(
        lambda: TelegramBotHttpClient(_require_live_send_token()),
        _require_allowed_chat,
    )


def _key(
    kind: str, chat: str, payload: dict[str, Any], scheduled: str, supplied: str | None
) -> str:
    if supplied is not None:
        supplied = supplied.strip()
        if not 1 <= len(supplied) <= 200:
            raise ValueError("idempotency_key must contain 1 to 200 non-whitespace characters")
        return supplied
    return "auto:" + hashlib.sha256(f"{kind}|{chat}|{scheduled}|{payload}".encode()).hexdigest()


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
        message_id = result.message_ids[-1] if result.message_ids else result.photo_message_id
        if payload.get("editorial_draft_id"):
            _editorial().link_delivery(payload["editorial_draft_id"], message_id)
        return message_id
    if item.kind == "poll":
        chat = _require_allowed_chat(item.chat_id)
        result = await TelegramBotHttpClient(_require_live_send_token()).send_poll(
            chat_id=chat, poll=item.payload
        )
        message_id = _message_id(result, operation="sendPoll")
        poll_id = _poll_id(result)
        poll = result["poll"]
        assert isinstance(poll, dict)
        _polls().record_sent(poll=poll, chat_id=chat, message_id=message_id)
        if str(poll.get("id")) != poll_id:
            raise RuntimeError("Telegram poll identifier changed during validation")
        return message_id
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
    """Return Telegram MCP configuration status without secrets or local filesystem paths."""
    return {
        "configured": bool((settings.telegram_bot_token or "").strip()),
        "allowed_chat_ids_count": len(_allowed_chat_ids()),
        "outbound_enabled": bool(_allowed_chat_ids()) and _live_send_enabled(),
        "live_send_enabled": _live_send_enabled(),
        "scheduler_persistence_configured": bool(settings.telegram_scheduler_db_path.strip()),
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
    editorial_draft_id: str | None = None,
) -> dict[str, Any]:
    """Persist an allowlisted text/photo publication for a future timezone-aware time."""
    chat = _require_allowed_chat(chat_id)
    if not text or not text.strip():
        raise ValueError("text must not be empty")
    if photo_url and photo_base64:
        raise ValueError("provide only one of photo_url or photo_base64")
    if photo_base64:
        validate_photo_bytes(_decode_photo_base64(photo_base64))
    if photo_url:
        photo_url = validate_photo_url(photo_url)
    filename = validate_filename(filename)
    scheduled = parse_schedule_time(scheduled_for)
    payload = {
        "text": text,
        "photo_url": photo_url,
        "photo_base64": photo_base64,
        "filename": filename,
        "editorial_draft_id": editorial_draft_id,
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
async def telegram_reconcile_delivery(schedule_id: str, outcome: str, operator: str, evidence_note: str) -> dict[str, Any]:
    """Manually reconcile an uncertain dispatch; this never re-sends a Telegram publication."""
    return _scheduled(_store().reconcile(schedule_id, outcome=outcome, operator=operator, evidence_note=evidence_note))


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
    result = await TelegramBotHttpClient(_require_live_send_token()).send_poll(
        chat_id=chat, poll=poll
    )
    message_id = _message_id(result, operation="sendPoll")
    poll_id = _poll_id(result)
    returned_poll = result["poll"]
    assert isinstance(returned_poll, dict)
    _polls().record_sent(poll=returned_poll, chat_id=chat, message_id=message_id)
    return {
        "ok": True,
        "chat_id": chat,
        "message_id": message_id,
        "poll_id": poll_id,
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
    """Return poll results only while the owning chat remains allowlisted."""
    poll_key = poll_id.strip()
    if not poll_key:
        raise ValueError("poll_id must not be empty")
    result = _polls().results(poll_key)
    chat_id = result.get("chat_id")
    if chat_id is None:
        raise PermissionError("poll is not bound to an allowlisted Telegram chat")
    _require_allowed_chat(chat_id)
    return result


def _editorial_mode(mode: str | None) -> str:
    value = (mode or settings.telegram_editorial_mode).upper()
    if value not in {"DRAFT", "APPROVE", "AUTO"}:
        raise ValueError("mode must be DRAFT, APPROVE, or AUTO")
    return value


@mcp.tool()
async def telegram_editorial_plan_week(
    week_start: str,
    topics: list[str],
    rubrics: list[str] | None = None,
    publishing_windows: list[str] | None = None,
    series_length: int | None = None,
) -> dict[str, Any]:
    """Persist a non-repetitive weekly editorial plan; windows are UTC HH:MM values."""
    try:
        start = __import__("datetime").date.fromisoformat(week_start)
    except ValueError as exc:
        raise ValueError("week_start must be YYYY-MM-DD") from exc
    items = _editorial().create_plan(
        week_start=start,
        topics=topics,
        rubrics=rubrics or list(DEFAULT_RUBRICS),
        windows=publishing_windows or ["09:00"],
        series_length=series_length,
    )
    return {"items": [item.__dict__ for item in items]}


@mcp.tool()
async def telegram_editorial_list_plan(week_start: str | None = None) -> dict[str, Any]:
    """List persistent planned editorial items."""
    return {"items": [item.__dict__ for item in _editorial().list_items(week_start)]}


@mcp.tool()
async def telegram_editorial_update_plan_item(
    item_id: str, topic: str | None = None, scheduled_for: str | None = None
) -> dict[str, Any]:
    """Update a persistent plan item before it becomes a scheduled publication."""
    return _editorial().update_item(item_id, topic=topic, scheduled_for=scheduled_for).__dict__


@mcp.tool()
async def telegram_editorial_cancel_plan_item(item_id: str) -> dict[str, Any]:
    """Cancel a planned item; a separately scheduled publication must be cancelled by schedule ID."""
    return _editorial().update_item(item_id, state="cancelled").__dict__


@mcp.tool()
async def telegram_editorial_generate_draft(
    item_id: str | None = None,
    topic: str | None = None,
    rubric: str | None = None,
    body: str | None = None,
    mode: str | None = None,
    image_url: str | None = None,
    photo_base64: str | None = None,
    image_prompt: str | None = None,
) -> dict[str, Any]:
    """Generate/store a reviewable draft. AUTO only approves low-risk material."""
    editorial_mode = _editorial_mode(mode)
    item = _editorial().get_item(item_id) if item_id else None
    topic, rubric = (
        topic or (item.topic if item else None),
        rubric or (item.rubric if item else "профессиональный взгляд/наблюдение"),
    )
    if not topic:
        raise ValueError("topic or item_id is required")
    headline = f"{rubric.capitalize()}: {topic}"
    content = (
        body
        or f"{headline}\n\nКороткий профессиональный разбор темы «{topic}». Делитесь своим опытом в комментариях."
    )
    draft = _editorial().create_draft(
        item_id=item.id if item else None,
        headline=headline,
        body=content,
        mode=editorial_mode,
        image_url=image_url,
        photo_base64=photo_base64,
        image_prompt=image_prompt,
    )
    return draft


@mcp.tool()
async def telegram_editorial_safety_check(text: str) -> dict[str, Any]:
    """Run a structured publication safety gate; it is not definitive legal clearance."""
    return safety_check(text)


@mcp.tool()
async def telegram_editorial_approve(draft_id: str) -> dict[str, Any]:
    """Explicitly approve a draft after human review."""
    draft = _editorial().get_draft(draft_id)
    if draft["state"] == "rejected":
        raise ValueError("rejected draft cannot be approved")
    return _editorial().set_draft_state(draft_id, "approved")


@mcp.tool()
async def telegram_editorial_reject(draft_id: str) -> dict[str, Any]:
    """Reject a draft so it cannot be scheduled."""
    return _editorial().set_draft_state(draft_id, "rejected")


@mcp.tool()
async def telegram_editorial_schedule_approved(
    draft_id: str,
    chat_id: int | str,
    scheduled_for: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Schedule only an explicitly approved draft through the existing secure scheduler."""
    draft = _editorial().get_draft(draft_id)
    if draft["state"] != "approved":
        raise PermissionError("draft requires explicit approval before scheduling")
    # A high-risk AUTO draft reaches this point only after explicit human approval.
    when = scheduled_for
    if not when and draft["item_id"]:
        when = _editorial().get_item(draft["item_id"]).scheduled_for
    if not when:
        raise ValueError("scheduled_for is required when the draft has no planned item")
    response = await telegram_schedule_post(
        chat_id=chat_id,
        text=draft["body"],
        scheduled_for=when,
        photo_url=draft["image_url"],
        photo_base64=draft["photo_base64"],
        idempotency_key=idempotency_key or f"editorial:{draft_id}",
        editorial_draft_id=draft_id,
    )
    # Preserve linkage without returning image bytes or modifying base scheduler semantics.
    with _editorial()._connect() as con:
        con.execute(
            "UPDATE telegram_editorial_drafts SET scheduled_id=?, state='scheduled', updated_at=? WHERE id=?",
            (
                response["schedule_id"],
                __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
                draft_id,
            ),
        )
    return response


@mcp.tool()
async def telegram_editorial_from_transcript(
    transcript: str, item_id: str | None = None, mode: str | None = None
) -> dict[str, Any]:
    """Turn a transcript into a redacted draft; audio transcription can be plugged in upstream later."""
    clean = redact_transcript(transcript)
    if not clean:
        raise ValueError("transcript has no usable content")
    return await telegram_editorial_generate_draft(
        item_id=item_id, topic=clean[:80], body=clean, mode=mode
    )


@mcp.tool()
async def telegram_editorial_suggest_poll(draft_id: str) -> dict[str, Any]:
    """Propose, but never auto-publish, a concise engagement poll for an editorial draft."""
    draft = _editorial().get_draft(draft_id)
    topic = draft["headline"][:120]
    return {
        "draft_id": draft_id,
        "requires_approval": True,
        "question": f"Что разобрать дальше: {topic}?",
        "options": ["Практические ошибки", "Позиция защиты", "Судебная практика"],
    }


@mcp.tool()
async def telegram_editorial_performance() -> dict[str, Any]:
    """Report locally tracked publication data; unavailable Telegram metrics remain null."""
    return {"items": _editorial().performance()}


@mcp.tool()
async def telegram_editorial_best_topics() -> dict[str, Any]:
    """Group only collected publication records; no unsupported engagement metric is invented."""
    items = _editorial().performance()
    counts: dict[str, int] = {}
    for item in items:
        if item["rubric"]:
            counts[item["rubric"]] = counts.get(item["rubric"], 0) + 1
    return {
        "ranked_rubrics": sorted(
            ({"rubric": key, "published_count": value} for key, value in counts.items()),
            key=lambda row: row["published_count"],
            reverse=True,
        ),
        "basis": "published_count only; engagement metrics unavailable",
    }


@mcp.tool()
async def telegram_editorial_suggest_followup(draft_id: str) -> dict[str, Any]:
    """Suggest a follow-up based on an existing draft without claiming unavailable Telegram metrics."""
    draft = _editorial().get_draft(draft_id)
    return {
        "draft_id": draft_id,
        "suggestion": f"Продолжение: практические выводы по теме «{draft['headline']}»",
        "basis": "local editorial linkage; no unavailable engagement metrics inferred",
    }


@mcp.tool()
async def telegram_editorial_mark_evergreen(draft_id: str) -> dict[str, Any]:
    """Mark an existing draft evergreen; any repost still requires draft safety/approval flow."""
    return _editorial().mark_evergreen(draft_id)


@mcp.tool()
async def telegram_editorial_list_evergreen() -> dict[str, Any]:
    """Find prior evergreen posts; availability/performance is limited to locally tracked data."""
    return {"items": _editorial().evergreen()}


@mcp.tool()
async def telegram_editorial_prepare_repost(draft_id: str) -> dict[str, Any]:
    """Create an updated repost draft; it always re-enters APPROVE safety/approval flow."""
    source = _editorial().get_draft(draft_id)
    if not source["evergreen"]:
        raise ValueError("mark the source draft evergreen before preparing a repost")
    return _editorial().create_draft(
        item_id=None,
        headline=f"Обновлено: {source['headline']}",
        body=source["body"],
        mode="APPROVE",
        image_url=source["image_url"],
        photo_base64=source["photo_base64"],
        image_prompt=source["image_prompt"],
    )


# Media automation tools are persistence and drafting helpers.  They never send directly;
# publication must use telegram_editorial_schedule_approved / telegram_schedule_post.
@mcp.tool()
async def telegram_content_plan_create(week_start: str, topics: list[str], count: int = 7) -> dict[str, Any]:
    return _media().create_plan(week_start, topics, count=count)


@mcp.tool()
async def telegram_content_plan_get(plan_id: str) -> dict[str, Any]:
    return _media().get_plan(plan_id)


@mcp.tool()
async def telegram_content_plan_update(plan_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return _media().update_plan(plan_id, items)


@mcp.tool()
async def telegram_content_plan_replace_item(plan_id: str, position: int, topic: str, category: str = "law_changes") -> dict[str, Any]:
    plan = _media().get_plan(plan_id)
    if category not in __import__("jafar.telegram_media", fromlist=["CATEGORIES"]).CATEGORIES:
        raise ValueError("unknown_category")
    for item in plan["items"]:
        if item["position"] == position:
            item.update(topic=topic, category=category, state="breaking_news_replacement")
            return _media().update_plan(plan_id, plan["items"])
    raise KeyError(position)


@mcp.tool()
async def telegram_news_ingest(source_url: str, source_name: str, title: str, published_at: str | None = None, verified: bool = False, relevance: float = 0.0) -> dict[str, Any]:
    return _media().ingest_news(source_url=source_url, source_name=source_name, title=title, published_at=published_at, verified=verified, relevance=relevance)


@mcp.tool()
async def telegram_news_score(news_id: str, relevance: float) -> dict[str, Any]:
    if not 0 <= relevance <= 1:
        raise ValueError("relevance_must_be_between_0_and_1")
    return {"news_id": news_id, "relevance": relevance, "recommendation": "ignore" if relevance < .35 else "add_to_plan" if relevance < .75 else "breaking_news"}


@mcp.tool()
async def telegram_news_suggest_post(title: str, relevance: float = 0.5, verified: bool = False) -> dict[str, Any]:
    recommendation = "ignore" if relevance < .35 else "breaking_news" if verified and relevance >= .75 else "add_to_plan"
    return {"recommendation": recommendation, "requires_verification": not verified, "title": title}


@mcp.tool()
async def telegram_generate_post(topic: str, category: str = "real_legal_practice", facts: str = "") -> dict[str, Any]:
    if _editorial_router is not None:
        routed = _editorial_router.run(ModelRequest(prompt=f"Создай пост для Telegram: {topic}\n{facts}", task="editorial_generation", confidential=True))
        generated = generate_post(topic, category, routed[0].text)
        generated["model_routing"] = {"provider": routed[0].provider, "model": routed[0].model}
    else:
        generated = generate_post(topic, category, facts)
    return _media().save("post", generated)


@mcp.tool()
async def telegram_generate_short_post(topic: str, category: str = "real_legal_practice", facts: str = "") -> dict[str, Any]:
    from jafar.telegram_media import generate_post as _generate
    return _media().save("post", _generate(topic, category, facts, short=True))


@mcp.tool()
async def telegram_generate_breaking_post(title: str, facts: str, source_url: str, verified: bool = False) -> dict[str, Any]:
    if not verified:
        raise PermissionError("breaking_news_requires_verification")
    result = generate_post(title, "law_changes", facts)
    result["source_url"] = source_url
    return _media().save("breaking_post", result)


@mcp.tool()
async def telegram_rewrite_post(text: str, instruction: str = "сделать понятнее") -> dict[str, Any]:
    if not text.strip():
        raise ValueError("text_required")
    return _media().save("rewrite", {"text": text.strip(), "instruction": instruction, "mode": "APPROVE", "requires_approval": True})


@mcp.tool()
async def telegram_case_to_post(facts: str, procedural_violations: str = "", defense_strategy: str = "", planned_steps: str = "") -> dict[str, Any]:
    text, findings = redact_case("\n".join(filter(None, (facts, procedural_violations, defense_strategy, planned_steps))))
    result = generate_post("Реальная практика: анонимизированный разбор", "real_legal_practice", text)
    result.update(anonymized=True, confidentiality_findings=findings, safety_flag=bool(findings), requires_approval=True)
    return _media().save("case_post", result)


@mcp.tool()
async def telegram_comment_classify(text: str) -> dict[str, Any]:
    from jafar.comment_classifier import CommentIntent, classify_comment
    intent = classify_comment(text)
    mapping = {CommentIntent.DISCUSSION: "normal", CommentIntent.QUESTION: "question", CommentIntent.AGGRESSIVE: "aggressive", CommentIntent.LEGAL_HELP: "legal_question", CommentIntent.PERSONAL_DATA: "sensitive", CommentIntent.ESCALATE: "sensitive"}
    kind = mapping[intent]
    return {"classification": kind, "intent": intent.value, "requires_approval": kind in {"legal_question", "sensitive"}}


@mcp.tool()
async def telegram_comment_reply_draft(text: str) -> dict[str, Any]:
    classification = await telegram_comment_classify(text)
    return {"reply": "Спасибо за вопрос. В общем случае многое зависит от обстоятельств; обсудите ситуацию с адвокатом.", "classification": classification, "mode": "APPROVE", "requires_approval": classification["requires_approval"]}


@mcp.tool()
async def telegram_image_brief(topic: str, aspect_ratio: str = "4:5", cover_category: str = "editorial") -> dict[str, Any]:
    if aspect_ratio not in {"4:5", "1:1"}:
        raise ValueError("aspect_ratio_must_be_4:5_or_1:1")
    return _media().save("image_brief", {"topic": topic, "aspect_ratio": aspect_ratio, "cover_category": cover_category, "status": "requested", "provider": None})


@mcp.tool()
async def telegram_attach_image_to_draft(draft_id: str, image_path: str | None = None, image_url: str | None = None, image_prompt: str | None = None) -> dict[str, Any]:
    if sum(bool(x) for x in (image_path, image_url, image_prompt)) != 1:
        raise ValueError("provide_exactly_one_image_reference")
    return _media().save("image_attachment", {"draft_id": draft_id, "image_path": image_path, "image_url": image_url, "image_prompt": image_prompt, "status": "attached"})


@mcp.tool()
async def telegram_series_create(title: str, parts: int, topics: list[str]) -> dict[str, Any]:
    if not 2 <= parts <= 10 or len(topics) < parts:
        raise ValueError("series_requires_2_to_10_parts_and_topics")
    return _media().save("series", {"title": title, "parts": [{"number": i + 1, "topic": topics[i], "state": "planned"} for i in range(parts)]})


@mcp.tool()
async def telegram_series_generate(series_id: str) -> dict[str, Any]:
    return {"series_id": series_id, "requires_approval": True, "parts": []}


@mcp.tool()
async def telegram_series_schedule(series_id: str, schedule: list[str]) -> dict[str, Any]:
    if len(schedule) < 2:
        raise ValueError("series_schedule_requires_multiple_dates")
    return {"series_id": series_id, "schedule": schedule, "status": "planned"}


@mcp.tool()
async def telegram_engagement_suggest(draft_id: str) -> dict[str, Any]:
    return {"draft_id": draft_id, "suggestion": "poll", "question": "Какую тему разобрать дальше?", "options": ["Ошибки следствия", "Работа адвоката", "Истории из практики"], "requires_approval": True}


@mcp.tool()
async def telegram_followup_suggest(draft_id: str) -> dict[str, Any]:
    return {"draft_id": draft_id, "suggestion": "part_2", "requires_approval": True, "basis": "editorial linkage only"}


@mcp.tool()
async def telegram_content_performance() -> dict[str, Any]:
    return await telegram_editorial_performance()


@mcp.tool()
async def telegram_content_best_topics() -> dict[str, Any]:
    return await telegram_editorial_best_topics()


@mcp.tool()
async def telegram_content_recommend_next() -> dict[str, Any]:
    return {"topics": list(DEFAULT_RUBRICS), "basis": "available editorial categories; no invented engagement metrics"}


@mcp.tool()
async def telegram_content_metrics_ingest(message_id: int, views: int | None = None, reactions: int | None = None, comments: int | None = None) -> dict[str, Any]:
    """Persist only metrics observed from Telegram updates/API responses."""
    return _media().save_metrics(message_id=message_id, views=views, reactions=reactions, comments=comments)


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
