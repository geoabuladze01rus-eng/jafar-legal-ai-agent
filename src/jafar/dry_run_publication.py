from __future__ import annotations

import asyncio

from .publication_dispatch import TelegramSendResult
from .publication_runtime import DispatchablePublication, dispatch_publication


class DryRunSender:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_text(self, *, chat_id: str, text: str) -> TelegramSendResult:
        self.sent.append({"type": "text", "chat_id": chat_id, "text": text})
        return TelegramSendResult(message_id=0, chat_id=chat_id)

    async def send_media(self, *, chat_id: str, media_type: str, media_url: str, caption: str) -> TelegramSendResult:
        self.sent.append({
            "type": media_type,
            "chat_id": chat_id,
            "media_url": media_url,
            "caption": caption,
        })
        return TelegramSendResult(message_id=0, chat_id=chat_id)


class DryRunStore:
    def __init__(self) -> None:
        self.published: list[tuple[int, int]] = []
        self.failed: list[tuple[int, str]] = []

    async def mark_published(self, publication_id: int, message_id: int) -> None:
        self.published.append((publication_id, message_id))

    async def mark_failed(self, publication_id: int, reason: str) -> None:
        self.failed.append((publication_id, reason))


async def run_dry_run() -> dict[str, object]:
    sender = DryRunSender()
    store = DryRunStore()
    item = DispatchablePublication(
        publication_id=1,
        chat_id="@iznanka_ugolovki",
        body="🚨 ТЕСТОВЫЙ ПОСТ — DRY RUN\n\nЭто проверка контура публикации. Сообщение НЕ отправляется в Telegram.\n\n#тест #право #уголовноедело",
    )
    message_id = await dispatch_publication(item, sender, store)
    return {
        "sent": sender.sent,
        "published": store.published,
        "failed": store.failed,
        "message_id": message_id,
    }


def main() -> None:
    result = asyncio.run(run_dry_run())
    print("DRY_RUN_OK")
    print(result)


if __name__ == "__main__":
    main()
