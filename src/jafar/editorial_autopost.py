from __future__ import annotations

import base64
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import settings

TELEGRAM_TEXT_LIMIT = 4096

EDITORIAL_SYSTEM_PROMPT = """
Ты — главный редактор Telegram-канала «Уголовка наизнанку».

Автор — Артур Чернов, юрист и бывший следователь. Он НЕ является адвокатом.
Никогда не называй его адвокатом и не создавай впечатление такого статуса.

Задача канала — объяснять человеческим языком, как уголовный процесс реально работает
изнутри: логика следователя, ошибки и нарушения, практические риски, экономические дела,
обыски, задержания, допросы, меры пресечения, арест имущества, судебная практика
и значимые изменения законодательства.

Стиль: живой, уверенный, профессиональный, иногда жёсткий, но без истерики,
дешёвого кликбейта и канцелярита. Короткие абзацы.
Сильная структура: HOOK → ситуация → конфликт → объяснение автора → практический вывод
→ CTA только если он действительно уместен.

Достоверность:
- используй только факты из переданного исходного материала;
- не выдумывай нормы, судебные акты, номера дел, даты, цитаты и обстоятельства;
- если правовой тезис требует внешней проверки, внеси его в legal_claims;
- отделяй подтверждённый факт от позиции стороны и авторской оценки;
- реальные дела обезличивай;
- не раскрывай непубличную стратегию защиты;
- не смешивай разные дела;
- новости не пересказывай: обязательно добавь профессиональный угол автора.

Визуал:
- image_prompt должен описывать один кинематографичный реалистичный кадр;
- тёмная графитово-синяя палитра, холодный направленный свет, минимализм;
- атмосфера документальности и уголовной юстиции;
- без текста, логотипов, узнаваемых участников реального дела и персональных данных;
- без карикатур и дешёвых фотостоковых клише.

Верни только валидный JSON без markdown.
JSON-схема:
{
  "title": "короткий заголовок",
  "hook": "1-3 строки",
  "body": "основной текст",
  "cta": null,
  "image_prompt": "промпт визуала",
  "legal_claims": [],
  "risk": "green",
  "risk_flags": [],
  "author_value_add": "почему именно автор добавляет ценность"
}

risk:
green — вечнозелёный безопасный материал без текущего дела и непроверенных правовых тезисов;
yellow — новость, судебная практика, изменение закона или правовой тезис на проверку;
red — текущее дело, чувствительные факты, персональные данные или риск для процессуальной позиции.
""".strip()

VISUAL_STYLE_PREFIX = (
    "Кинематографичный реалистичный кадр для авторского юридического Telegram-канала. "
    "Тёмная графитово-синяя палитра, чёрный и холодный серый, направленный холодный свет, "
    "минимализм, ощущение напряжения и документальности. "
    "Без текста, логотипов, водяных знаков, узнаваемых лиц реальных участников, "
    "персональных данных и карикатур. "
)


class EditorialRisk(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class EditorialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=500)
    source_text: str = Field(min_length=1)
    source_urls: list[str] = Field(default_factory=list)
    is_news: bool = False
    current_case: bool = False


class EditorialDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=180)
    hook: str = Field(min_length=1, max_length=700)
    body: str = Field(min_length=1, max_length=7000)
    cta: str | None = Field(default=None, max_length=700)
    image_prompt: str = Field(min_length=1, max_length=2000)
    legal_claims: list[str] = Field(default_factory=list)
    risk: EditorialRisk = EditorialRisk.YELLOW
    risk_flags: list[str] = Field(default_factory=list)
    author_value_add: str | None = Field(default=None, max_length=1200)

    @field_validator("title", "hook", "body", "image_prompt")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("editorial text field must not be blank")
        return value

    @model_validator(mode="after")
    def telegram_length_guard(self) -> EditorialDraft:
        if len(self.render_text()) > TELEGRAM_TEXT_LIMIT:
            raise ValueError("rendered Telegram post exceeds 4096 characters")
        return self

    def render_text(self) -> str:
        parts = [self.title, self.hook, self.body]
        if self.cta:
            parts.append(self.cta.strip())
        return "\n\n".join(part.strip() for part in parts if part and part.strip())


@dataclass(frozen=True, slots=True)
class EditorialBundle:
    request: EditorialRequest
    draft: EditorialDraft
    image_bytes: bytes


@dataclass(frozen=True, slots=True)
class EditorialQueueItem:
    publication_id: str
    request: EditorialRequest
    draft: EditorialDraft
    image_bytes: bytes
    status: str
    created_at: str
    updated_at: str


class DeepSeekEditorialProvider:
    """Structured editorial generation through DeepSeek's OpenAI-compatible API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        key = api_key or settings.deepseek_api_key
        if client is None and not key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for editorial generation")
        self.model = model or settings.deepseek_editorial_model
        self.client = client or OpenAI(
            api_key=key,
            base_url=base_url or settings.deepseek_base_url,
            timeout=120.0,
        )

    def generate(self, request: EditorialRequest) -> EditorialDraft:
        source_urls = "\n".join(f"- {url}" for url in request.source_urls) or "- не указаны"
        user_prompt = (
            "Сформируй готовый редакционный черновик в JSON.\n"
            f"Тема: {request.topic}\n"
            f"Новость: {'да' if request.is_news else 'нет'}\n"
            f"Текущее дело: {'да' if request.current_case else 'нет'}\n"
            f"Источники:\n{source_urls}\n\n"
            "Исходный материал:\n"
            f"{request.source_text}"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": EDITORIAL_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=6000,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("DeepSeek returned empty editorial JSON")
        draft = EditorialDraft.model_validate_json(content)
        return self._enforce_policy(draft, request)

    @staticmethod
    def _enforce_policy(draft: EditorialDraft, request: EditorialRequest) -> EditorialDraft:
        full_text = draft.render_text()
        if _misstates_author_status(full_text):
            raise ValueError("generated post incorrectly describes Arthur Chernov as an advocate")

        data = draft.model_dump()
        risk = draft.risk
        flags = list(draft.risk_flags)

        if request.current_case:
            risk = EditorialRisk.RED
            if "current_case" not in flags:
                flags.append("current_case")
        elif request.is_news or draft.legal_claims:
            if risk is EditorialRisk.GREEN:
                risk = EditorialRisk.YELLOW
            if request.is_news and "news_requires_review" not in flags:
                flags.append("news_requires_review")
            if draft.legal_claims and "legal_claims_require_factcheck" not in flags:
                flags.append("legal_claims_require_factcheck")

        data["risk"] = risk
        data["risk_flags"] = flags
        return EditorialDraft.model_validate(data)


class OpenAIEditorialImageProvider:
    """Generate a clean visual without text; typography can be added later deterministically."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        size: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        key = api_key or settings.openai_api_key
        if client is None and not key:
            raise RuntimeError("OPENAI_API_KEY is required for editorial image generation")
        self.client = client or OpenAI(api_key=key, timeout=180.0)
        self.model = model or settings.editorial_image_model
        self.size = size or settings.editorial_image_size

    def generate(self, image_prompt: str) -> bytes:
        response = self.client.images.generate(
            model=self.model,
            prompt=VISUAL_STYLE_PREFIX + image_prompt.strip(),
            size=self.size,
            quality="medium",
            output_format="jpeg",
            n=1,
        )
        if not response.data:
            raise RuntimeError("OpenAI image generation returned no image")
        item = response.data[0]

        b64 = getattr(item, "b64_json", None)
        if b64:
            return base64.b64decode(b64)

        url = getattr(item, "url", None)
        if url:
            image_response = httpx.get(url, timeout=60.0, follow_redirects=True)
            image_response.raise_for_status()
            return image_response.content

        raise RuntimeError("OpenAI image response did not include image data")


class EditorialAutopostService:
    def __init__(
        self,
        text_provider: DeepSeekEditorialProvider,
        image_provider: OpenAIEditorialImageProvider,
    ) -> None:
        self.text_provider = text_provider
        self.image_provider = image_provider

    def generate_bundle(self, request: EditorialRequest) -> EditorialBundle:
        draft = self.text_provider.generate(request)
        image_bytes = self.image_provider.generate(draft.image_prompt)
        if not image_bytes:
            raise RuntimeError("visual generation returned empty bytes")
        return EditorialBundle(request=request, draft=draft, image_bytes=image_bytes)


class EditorialQueueStore:
    """Small durable queue for one Djafar instance; no secrets are stored in the DB."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or settings.editorial_db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists editorial_queue (
                    publication_id text primary key,
                    request_json text not null,
                    draft_json text not null,
                    image_base64 text not null,
                    status text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )

    def create(self, bundle: EditorialBundle, *, status: str = "review") -> EditorialQueueItem:
        publication_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                insert into editorial_queue (
                    publication_id, request_json, draft_json, image_base64,
                    status, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    publication_id,
                    bundle.request.model_dump_json(),
                    bundle.draft.model_dump_json(),
                    base64.b64encode(bundle.image_bytes).decode("ascii"),
                    status,
                    now,
                    now,
                ),
            )
        return self.get(publication_id)

    def get(self, publication_id: str) -> EditorialQueueItem:
        with self._connect() as connection:
            row = connection.execute(
                "select * from editorial_queue where publication_id = ?",
                (publication_id,),
            ).fetchone()
        if row is None:
            raise KeyError(publication_id)
        return _row_to_item(row)

    def replace_bundle(self, publication_id: str, bundle: EditorialBundle) -> EditorialQueueItem:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update editorial_queue
                set request_json = ?, draft_json = ?, image_base64 = ?,
                    status = 'review', updated_at = ?
                where publication_id = ?
                """,
                (
                    bundle.request.model_dump_json(),
                    bundle.draft.model_dump_json(),
                    base64.b64encode(bundle.image_bytes).decode("ascii"),
                    now,
                    publication_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(publication_id)
        return self.get(publication_id)

    def replace_image(self, publication_id: str, image_bytes: bytes) -> EditorialQueueItem:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update editorial_queue
                set image_base64 = ?, status = 'review', updated_at = ?
                where publication_id = ?
                """,
                (
                    base64.b64encode(image_bytes).decode("ascii"),
                    now,
                    publication_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(publication_id)
        return self.get(publication_id)

    def set_status(self, publication_id: str, status: str) -> EditorialQueueItem:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                update editorial_queue
                set status = ?, updated_at = ?
                where publication_id = ?
                """,
                (status, now, publication_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(publication_id)
        return self.get(publication_id)


def _row_to_item(row: sqlite3.Row) -> EditorialQueueItem:
    return EditorialQueueItem(
        publication_id=str(row["publication_id"]),
        request=EditorialRequest.model_validate_json(row["request_json"]),
        draft=EditorialDraft.model_validate_json(row["draft_json"]),
        image_bytes=base64.b64decode(row["image_base64"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _misstates_author_status(text: str) -> bool:
    lowered = text.lower()
    patterns = (
        r"\bадвокат\s+артур(?:а|у|ом|е)?\s+чернов(?:а|у|ым|е)?\b",
        r"\bадвокат\s+чернов(?:а|у|ым|е)?\b",
        r"\bартур\s+чернов\s*[-—,:]?\s*адвокат\b",
    )
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns)


def editorial_request_from_payload(payload: dict[str, Any]) -> EditorialRequest:
    return EditorialRequest.model_validate(payload)


def editorial_response_payload(item: EditorialQueueItem) -> dict[str, Any]:
    return {
        "publication_id": item.publication_id,
        "status": item.status,
        "risk": item.draft.risk.value,
        "risk_flags": item.draft.risk_flags,
        "title": item.draft.title,
        "requires_approval": item.draft.risk is not EditorialRisk.GREEN,
    }
