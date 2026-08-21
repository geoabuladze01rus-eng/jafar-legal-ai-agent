from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MediaType(StrEnum):
    NONE = "none"
    IMAGE = "image"
    VIDEO = "video"


@dataclass(frozen=True)
class MediaPlan:
    media_type: MediaType
    prompt: str | None = None
    caption: str | None = None


def plan_media(*, topic: str, format: str, needs_visual: bool = False, needs_video: bool = False) -> MediaPlan:
    if needs_video:
        return MediaPlan(MediaType.VIDEO, prompt=f"Короткое вертикальное видео для юридического Telegram-поста на тему: {topic}. Формат: {format}.")
    if needs_visual:
        return MediaPlan(MediaType.IMAGE, prompt=f"Редакционная иллюстрация для юридического Telegram-поста на тему: {topic}. Формат: {format}. Без выдуманных документов, печатей или фактов.")
    return MediaPlan(MediaType.NONE)
