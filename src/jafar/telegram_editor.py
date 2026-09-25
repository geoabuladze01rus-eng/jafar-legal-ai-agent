from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .telegram_content_risk import TelegramContentRiskGuard
from .telegram_publication import (
    FactCheckResult,
    FactCheckStatus,
    PublicationStatus,
    PublicationType,
    TelegramPublication,
)


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


EDITOR_SYSTEM_PROMPT = """
Ты — AI-редактор авторского Telegram-канала «Уголовка наизнанку».

Автор канала — Артур Чернов, ЮРИСТ и бывший следователь с многолетним опытом.
Артур Чернов НЕ адвокат. Никогда не называй его адвокатом и не создавай впечатление,
что у него есть статус адвоката.

Позиционирование канала: объяснять, как уголовный процесс реально работает изнутри,
показывать логику следователя, процессуальные ошибки, практические риски для граждан
и бизнеса, судебную практику и то, что обычно остаётся за закрытой дверью кабинета
следователя.

Стиль: живой, уверенный, профессиональный, иногда жёсткий; короткие абзацы;
минимум канцелярита; без дешёвого кликбейта и истерики. Сильная структура:
HOOK → ситуация → конфликт/проблема → объяснение автора → практический вывод → CTA,
только если CTA действительно уместен.

Telegram-оформление обычного текстового/фото-поста:
- используй 2–5 уместных смысловых эмодзи на публикацию;
- допустим один эмодзи в hook, цифровые эмодзи 1️⃣–5️⃣ в практическом списке
  и один эмодзи у вывода/CTA;
- не ставь эмодзи внутрь точных цитат закона, номеров статей, судебных реквизитов;
- не делай «ёлку», не используй ряды декоративных эмодзи, огонь или сирены ради кликбейта.

Ты можешь предложить image_prompt для любого обычного поста. Но тип публикации имеет
строгое техническое значение: text — один текстовый Telegram message без обязательного
media; photo — один SendPhoto с обязательным approved visual asset. Если выбираешь photo,
AI не имеет права считать визуал одобренным: отдельный media-stage должен назначить
approved visual category и approved asset key. До назначения asset материал остаётся Review.
Никогда не понижай photo до text ради обхода media-stage в production.

Правила достоверности:
- не выдумывай факты, номера дел, судебные акты, нормы, даты, цитаты или источники;
- если правовой тезис требует проверки, вынеси его в legal_claims;
- не подменяй факт предположением;
- реальные дела по умолчанию обезличивай;
- не смешивай обстоятельства разных дел;
- при риске для текущего дела укажи это в risk_flags;
- профессиональные СМИ могут дать тему, но не заменяют официальный правовой источник.

Новость не должна быть простым пересказом. Для новостного материала обязательно сформулируй
author_value_add: что именно бывший следователь и практикующий юрист добавляет к известным фактам.
Если такого угла нет, оставь author_value_add пустым — система заблокирует материал.

Ты создаёшь только редакционный черновик. Ты НЕ одобряешь публикацию и не управляешь
статусом Ready/Published. Статуса публикации в твоей схеме вообще нет.
""".strip()


class StructuredEditorialProvider(Protocol):
    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredModel],
    ) -> StructuredModel: ...


class TelegramEditorialDraft(BaseModel):
    """AI-owned fields only. Deliberately has no publication status or message id."""

    model_config = ConfigDict(extra="forbid")

    title: str
    hook: str
    recommended_publication_type: PublicationType = PublicationType.TEXT
    content: str
    cta: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    image_prompt: str | None = None
    author_value_add: str | None = None
    legal_claims: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    recommended_publish_at: datetime | None = None

    question: str | None = None
    options: list[str] = Field(default_factory=list)
    correct_option_ids: list[int] = Field(default_factory=list)
    explanation: str | None = None

    @field_validator("title", "hook", "content")
    @classmethod
    def non_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("editorial text fields must not be blank")
        return value

    @model_validator(mode="after")
    def validate_editorial_type(self) -> TelegramEditorialDraft:
        if self.recommended_publish_at is not None and self.recommended_publish_at.tzinfo is None:
            raise ValueError("recommended_publish_at must be timezone-aware")
        if self.recommended_publication_type in {PublicationType.POLL, PublicationType.QUIZ}:
            if not (self.question or "").strip():
                raise ValueError("poll/quiz draft requires question")
            if not self.options:
                raise ValueError("poll/quiz draft requires options")
        if self.recommended_publication_type is PublicationType.QUIZ and not self.correct_option_ids:
            raise ValueError("quiz draft requires correct_option_ids")
        return self


@dataclass(frozen=True, slots=True)
class EditorialResult:
    draft: TelegramEditorialDraft
    publication: TelegramPublication


class TelegramEditorialService:
    def __init__(
        self,
        provider: StructuredEditorialProvider,
        *,
        risk_guard: TelegramContentRiskGuard | None = None,
    ) -> None:
        self.provider = provider
        self.risk_guard = risk_guard or TelegramContentRiskGuard()

    def create_publication(
        self,
        *,
        topic: str,
        source_text: str,
        source_title: str | None = None,
        source_url: str | None = None,
        is_news: bool = False,
        photo_url: str | None = None,
        visual_asset_key: str | None = None,
        visual_asset_id: str | None = None,
        visual_category: str | None = None,
        current_case: bool = False,
    ) -> EditorialResult:
        if not topic.strip():
            raise ValueError("topic must not be empty")
        if not source_text.strip():
            raise ValueError("source_text must not be empty")

        draft = self.provider.complete_structured(
            system_prompt=EDITOR_SYSTEM_PROMPT,
            user_prompt=self._user_prompt(
                topic=topic,
                source_text=source_text,
                source_title=source_title,
                source_url=source_url,
                is_news=is_news,
            ),
            response_model=TelegramEditorialDraft,
        )
        if not isinstance(draft, TelegramEditorialDraft):
            draft = TelegramEditorialDraft.model_validate(draft)

        blockers: list[str] = []
        if is_news and not (draft.author_value_add or "").strip():
            blockers.append("missing_author_value_add")
        if is_news and not source_url:
            blockers.append("news_source_url_missing")
        if _misstates_author_status("\n".join([draft.title, draft.hook, draft.content])):
            blockers.append("incorrect_author_status")
        if (
            draft.recommended_publication_type in {PublicationType.TEXT, PublicationType.PHOTO}
            and _emoji_count("\n".join([draft.hook, draft.content, draft.cta or ""])) < 2
        ):
            blockers.append("telegram_emoji_style_missing")

        visual_required = draft.recommended_publication_type is PublicationType.PHOTO
        if visual_required and not (visual_asset_key or "").strip():
            blockers.append("visual_asset_missing")
        if visual_required and not (visual_category or "").strip():
            blockers.append("visual_category_missing")

        full_text = "\n".join(
            part
            for part in [draft.title, draft.hook, draft.content, draft.cta or ""]
            if part
        )
        risk_assessment = self.risk_guard.assess(full_text, current_case=current_case)
        if any(flag.lower() in {"current_case", "current_case_risk"} for flag in draft.risk_flags):
            risk_assessment = self.risk_guard.assess(full_text, current_case=True)

        actual_type = draft.recommended_publication_type

        requires_fact_check = bool(draft.legal_claims)
        fact_check = FactCheckResult(
            status=FactCheckStatus.PENDING if requires_fact_check else FactCheckStatus.NOT_REQUIRED
        )
        publication = TelegramPublication(
            publication_type=actual_type,
            title=draft.title,
            content=draft.content,
            caption=draft.content if actual_type is PublicationType.PHOTO else None,
            cta=draft.cta,
            hashtags=draft.hashtags,
            image_prompt=draft.image_prompt,
            photo_url=photo_url,
            visual_required=visual_required,
            visual_asset_key=visual_asset_key,
            visual_asset_id=visual_asset_id,
            visual_category=visual_category,
            question=draft.question if actual_type in {PublicationType.POLL, PublicationType.QUIZ} else None,
            options=draft.options if actual_type in {PublicationType.POLL, PublicationType.QUIZ} else [],
            correct_option_ids=(
                draft.correct_option_ids if actual_type is PublicationType.QUIZ else []
            ),
            explanation=draft.explanation if actual_type is PublicationType.QUIZ else None,
            source_title=source_title,
            source_url=source_url,
            publish_at=draft.recommended_publish_at,
            status=PublicationStatus.REVIEW,
            requires_fact_check=requires_fact_check,
            fact_check=fact_check,
            risk=risk_assessment.risk,
            editorial_blockers=blockers,
        )
        return EditorialResult(draft=draft, publication=publication)

    @staticmethod
    def _user_prompt(
        *,
        topic: str,
        source_text: str,
        source_title: str | None,
        source_url: str | None,
        is_news: bool,
    ) -> str:
        return (
            f"Тема: {topic.strip()}\n"
            f"Это новостной инфоповод: {'да' if is_news else 'нет'}\n"
            f"Заголовок источника: {source_title or 'не указан'}\n"
            f"URL источника: {source_url or 'не указан'}\n\n"
            "Подготовь структурированный редакционный черновик только из подтверждаемого "
            "материала ниже. Если правовое утверждение требует внешней проверки, не выдавай "
            "его за установленный факт — добавь его в legal_claims.\n\n"
            f"Исходный материал:\n{source_text.strip()}"
        )


def _misstates_author_status(text: str) -> bool:
    patterns = (
        r"\bадвокат\s+артур(?:а|у|ом|е)?\s+чернов(?:а|у|ым|е)?\b",
        r"\bадвокат\s+чернов(?:а|у|ым|е)?\b",
        r"\bартур\s+чернов\s*[-—,:]?\s*адвокат\b",
    )
    lowered = text.lower()
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns)


def _emoji_count(text: str) -> int:
    pictograms = re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text)
    keycaps = re.findall(r"[0-9#*]\ufe0f?\u20e3", text)
    return len(pictograms) + len(keycaps)
