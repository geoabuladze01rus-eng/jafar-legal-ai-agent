from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator


TELEGRAM_TEXT_MAX = 4096
TELEGRAM_CAPTION_MAX = 1024
TELEGRAM_POLL_QUESTION_MAX = 300
TELEGRAM_POLL_OPTION_MAX = 100
TELEGRAM_POLL_OPTIONS_MAX = 12
TELEGRAM_QUIZ_EXPLANATION_MAX = 200


class PublicationType(StrEnum):
    TEXT = "text"
    PHOTO = "photo"
    POLL = "poll"
    QUIZ = "quiz"


class PublicationStatus(StrEnum):
    DRAFT = "Draft"
    REVIEW = "Review"
    READY = "Ready"
    IN_PROGRESS = "In progress"
    PUBLISHED = "Published"
    ERROR = "Error"


class FactCheckStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryState(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    SENT = "sent"
    UNCERTAIN = "uncertain"
    FAILED = "failed"


class SourceEvidence(BaseModel):
    title: str
    url: str
    authority_rank: int = Field(ge=1, le=7)
    verified: bool = False


class FactCheckResult(BaseModel):
    status: FactCheckStatus = FactCheckStatus.PENDING
    sources: list[SourceEvidence] = Field(default_factory=list)
    checked_at: datetime | None = None
    notes: str | None = None


class PublicationRisk(BaseModel):
    legal_risk: RiskLevel = RiskLevel.LOW
    privacy_risk: RiskLevel = RiskLevel.LOW
    current_case_risk: bool = False
    flags: list[str] = Field(default_factory=list)


class PublishDecision(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)


class TelegramPublication(BaseModel):
    publication_id: str | None = None
    platform: Literal["Telegram"] = "Telegram"
    publication_type: PublicationType

    title: str | None = None
    content: str = ""
    caption: str | None = None
    cta: str | None = None
    hashtags: list[str] = Field(default_factory=list)

    image_prompt: str | None = None
    photo_url: str | None = None
    visual_required: bool = False
    visual_asset_key: str | None = None
    visual_asset_id: str | None = None
    visual_category: str | None = None

    question: str | None = None
    options: list[str] = Field(default_factory=list)
    correct_option_ids: list[int] = Field(default_factory=list)
    explanation: str | None = None

    source_title: str | None = None
    source_url: str | None = None

    publish_at: datetime | None = None
    status: PublicationStatus = PublicationStatus.REVIEW
    telegram_message_id: int | None = None
    published_at: datetime | None = None
    last_error: str | None = None

    requires_fact_check: bool = True
    fact_check: FactCheckResult = Field(default_factory=FactCheckResult)
    risk: PublicationRisk = Field(default_factory=PublicationRisk)
    editorial_blockers: list[str] = Field(default_factory=list)
    delivery_state: DeliveryState = DeliveryState.PENDING

    @model_validator(mode="after")
    def validate_publication(self) -> TelegramPublication:
        if self.publish_at is not None and self.publish_at.tzinfo is None:
            raise ValueError("publish_at must be timezone-aware")
        if self.published_at is not None and self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")

        self.photo_url = _empty_to_none(self.photo_url)
        self.visual_asset_key = _empty_to_none(self.visual_asset_key)
        self.visual_asset_id = _empty_to_none(self.visual_asset_id)
        self.visual_category = _empty_to_none(self.visual_category)

        if self.publication_type is PublicationType.TEXT:
            if not self.content.strip():
                raise ValueError("text publication requires content")
            if len(self.content) > TELEGRAM_TEXT_MAX:
                raise ValueError(f"text exceeds Telegram limit of {TELEGRAM_TEXT_MAX} characters")

        elif self.publication_type is PublicationType.PHOTO:
            if (
                self.status not in {PublicationStatus.DRAFT, PublicationStatus.REVIEW}
                and not _is_http_url(self.photo_url)
                and not self.visual_asset_key
            ):
                raise ValueError(
                    "photo publication requires an http(s) photo_url or approved visual_asset_key"
                )
            effective_caption = (self.caption if self.caption is not None else self.content).strip()
            if len(effective_caption) > TELEGRAM_CAPTION_MAX:
                raise ValueError(
                    f"photo caption exceeds Telegram limit of {TELEGRAM_CAPTION_MAX} characters"
                )

        elif self.publication_type in {PublicationType.POLL, PublicationType.QUIZ}:
            question = (self.question or "").strip()
            if not question:
                raise ValueError("poll/quiz requires question")
            if len(question) > TELEGRAM_POLL_QUESTION_MAX:
                raise ValueError(
                    f"poll question exceeds Telegram limit of {TELEGRAM_POLL_QUESTION_MAX} characters"
                )
            if not 2 <= len(self.options) <= TELEGRAM_POLL_OPTIONS_MAX:
                raise ValueError(
                    f"poll/quiz requires 2-{TELEGRAM_POLL_OPTIONS_MAX} answer options"
                )
            for option in self.options:
                if not option.strip():
                    raise ValueError("poll/quiz options cannot be blank")
                if len(option) > TELEGRAM_POLL_OPTION_MAX:
                    raise ValueError(
                        f"poll option exceeds Telegram limit of {TELEGRAM_POLL_OPTION_MAX} characters"
                    )

            if self.publication_type is PublicationType.QUIZ:
                if not self.correct_option_ids:
                    raise ValueError("quiz requires correct_option_ids")
                if sorted(set(self.correct_option_ids)) != self.correct_option_ids:
                    raise ValueError("correct_option_ids must be unique and monotonically increasing")
                if any(index < 0 or index >= len(self.options) for index in self.correct_option_ids):
                    raise ValueError("correct_option_ids contains an out-of-range option index")
                if self.explanation is not None:
                    if len(self.explanation) > TELEGRAM_QUIZ_EXPLANATION_MAX:
                        raise ValueError(
                            "quiz explanation exceeds Telegram limit of "
                            f"{TELEGRAM_QUIZ_EXPLANATION_MAX} characters"
                        )
                    if self.explanation.count("\n") > 2:
                        raise ValueError("quiz explanation may contain at most 2 line feeds")
            elif self.correct_option_ids:
                raise ValueError("regular poll must not define correct_option_ids")

        if self.telegram_message_id is not None and self.status is not PublicationStatus.PUBLISHED:
            raise ValueError("telegram_message_id requires Published status")
        if self.status is PublicationStatus.PUBLISHED and self.telegram_message_id is None:
            raise ValueError("Published status requires telegram_message_id")

        self.editorial_blockers = sorted(set(item.strip() for item in self.editorial_blockers if item.strip()))
        if self.publication_id is None:
            self.publication_id = build_publication_id(self)
        return self

    @property
    def content_fingerprint(self) -> str:
        canonical = "\x1f".join(
            [
                self.platform,
                self.publication_type.value,
                _normalize(self.title or ""),
                _normalize(self.source_url or ""),
                _normalize(self.content),
                _normalize(self.caption or ""),
                _normalize(self.question or ""),
                json.dumps(self.options, ensure_ascii=False, separators=(",", ":")),
                _normalize(self.visual_asset_key or ""),
                _normalize(self.visual_asset_id or ""),
                _normalize(self.visual_category or ""),
            ]
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def publish_decision(self, *, now: datetime | None = None) -> PublishDecision:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")

        reasons: list[str] = []
        if self.status is not PublicationStatus.READY:
            reasons.append("status_not_ready")
        if self.publish_at is not None and self.publish_at > now:
            reasons.append("publish_time_not_due")
        if self.telegram_message_id is not None or self.status is PublicationStatus.PUBLISHED:
            reasons.append("already_published")
        if self.delivery_state is not DeliveryState.PENDING:
            reasons.append(f"delivery_state_{self.delivery_state.value}")
        if self.editorial_blockers:
            reasons.extend(f"editorial:{item}" for item in self.editorial_blockers)
        if self.fact_check.status not in {
            FactCheckStatus.VERIFIED,
            FactCheckStatus.NOT_REQUIRED,
        }:
            reasons.append("fact_check_not_verified")
        if self.risk.current_case_risk:
            reasons.append("current_case_risk")
        if self.risk.privacy_risk is not RiskLevel.LOW:
            reasons.append("privacy_risk_requires_review")
        if self.risk.legal_risk is not RiskLevel.LOW:
            reasons.append("legal_risk_requires_review")
        if self.visual_required:
            if not self.visual_asset_key:
                reasons.append("visual_asset_missing")
            if not self.visual_category:
                reasons.append("visual_category_missing")
            if self.publication_type is PublicationType.TEXT:
                reasons.append("visual_required_but_text")
        if self.publication_type is PublicationType.PHOTO:
            if not self.visual_asset_key:
                reasons.append("visual_asset_key_missing")
            if not self.visual_required and not self.visual_category:
                reasons.append("visual_category_missing")
        return PublishDecision(allowed=not reasons, reasons=reasons)

    def telegram_payload(
        self,
        *,
        chat_id: int | str,
        resolved_photo: str | bytes | None = None,
    ) -> dict[str, Any]:
        if self.publication_type is PublicationType.TEXT:
            return {"method": "sendMessage", "chat_id": chat_id, "text": self.content}
        if self.publication_type is PublicationType.PHOTO:
            photo: str | bytes | None = resolved_photo or self.photo_url
            if photo is None:
                if self.visual_asset_key:
                    raise ValueError(
                        "visual_asset_key must be resolved to photo bytes or URL before sendPhoto"
                    )
                raise ValueError("photo payload is missing media")
            payload: dict[str, Any] = {
                "method": "sendPhoto",
                "chat_id": chat_id,
                "photo": photo,
            }
            effective_caption = self.caption if self.caption is not None else self.content
            if effective_caption:
                payload["caption"] = effective_caption
            return payload

        payload = {
            "method": "sendPoll",
            "chat_id": chat_id,
            "question": self.question,
            "options": [{"text": option} for option in self.options],
            "is_anonymous": True,
            "type": "quiz" if self.publication_type is PublicationType.QUIZ else "regular",
        }
        if self.publication_type is PublicationType.QUIZ:
            payload["correct_option_ids"] = self.correct_option_ids
            if self.explanation:
                payload["explanation"] = self.explanation
        return payload

    @classmethod
    def from_legacy_notion_fields(cls, fields: dict[str, Any]) -> TelegramPublication:
        publication_type = PublicationType(str(fields.get("Publication Type", "text")))
        options = parse_options_json(fields.get("Options JSON"))
        correct_ids: list[int] = []
        new_correct = fields.get("Correct Option IDs JSON")
        legacy_correct = fields.get("Correct Option ID")
        if publication_type is PublicationType.QUIZ:
            if new_correct not in (None, ""):
                parsed_correct = json.loads(str(new_correct))
                if not isinstance(parsed_correct, list):
                    raise ValueError("Correct Option IDs JSON must be a JSON array")
                correct_ids = [int(item) for item in parsed_correct]
            elif legacy_correct not in (None, ""):
                correct_ids = [int(legacy_correct)]
        return cls(
            publication_id=_empty_to_none(fields.get("Publication ID")),
            publication_type=publication_type,
            title=_empty_to_none(fields.get("Name")),
            content=str(fields.get("Content") or ""),
            caption=_empty_to_none(fields.get("Caption")),
            cta=_empty_to_none(fields.get("CTA")),
            image_prompt=_empty_to_none(fields.get("Image Prompt")),
            photo_url=_empty_to_none(fields.get("Photo URL")),
            visual_required=_coerce_bool(fields.get("Visual Required")),
            visual_asset_key=_empty_to_none(fields.get("Visual Asset Key")),
            visual_asset_id=_empty_to_none(fields.get("Visual Drive File ID")),
            visual_category=_empty_to_none(fields.get("Visual Category")),
            question=_empty_to_none(fields.get("Question")),
            options=options,
            correct_option_ids=correct_ids,
            explanation=_empty_to_none(fields.get("Explanation")),
            source_title=_empty_to_none(fields.get("Source Title")),
            source_url=_empty_to_none(fields.get("Source URL")),
            publish_at=_coerce_datetime(fields.get("Publish Date")),
            status=PublicationStatus(str(fields.get("Status") or PublicationStatus.REVIEW.value)),
            telegram_message_id=_coerce_int(fields.get("Telegram Message ID")),
            published_at=_coerce_datetime(fields.get("Published At")),
            last_error=_empty_to_none(fields.get("Last Error")),
            delivery_state=DeliveryState(str(fields.get("Delivery State") or DeliveryState.PENDING.value)),
        )


def parse_options_json(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError("Options JSON must be a JSON array")
    options: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            options.append(item)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            options.append(item["text"])
        else:
            raise ValueError("Each poll option must be a string or an object with text")
    return options


def build_publication_id(publication: TelegramPublication) -> str:
    seed_parts = [
        _normalize(publication.source_url or ""),
        publication.publication_type.value,
        _normalize(publication.title or ""),
    ]
    if not any(seed_parts[::2]):
        seed_parts.append(publication.content_fingerprint)
    digest = hashlib.sha256("\x1f".join(seed_parts).encode("utf-8")).hexdigest()[:24]
    return f"tg_{digest}"


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _is_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _empty_to_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).upper() in {"__YES__", "TRUE", "1", "YES"}


def _coerce_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)
