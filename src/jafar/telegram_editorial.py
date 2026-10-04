from __future__ import annotations

from typing import Any, Protocol

from .editorial_autopost import (
    EditorialAutopostService,
    EditorialQueueItem,
    EditorialQueueStore,
    EditorialRequest,
    EditorialRisk,
    editorial_response_payload,
)


class TelegramEditorialBot(Protocol):
    async def send_message(
        self,
        *,
        chat_id: int | str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def send_photo(
        self,
        *,
        chat_id: int | str,
        photo: bytes,
        filename: str = "editorial.jpg",
        caption: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
    ) -> dict[str, Any]: ...


class TelegramEditorialController:
    """Owner-review and publish boundary for Djafar editorial automation."""

    def __init__(
        self,
        *,
        bot: TelegramEditorialBot,
        service: EditorialAutopostService,
        store: EditorialQueueStore,
        owner_user_id: str,
        owner_chat_id: str,
        channel_id: str,
        auto_publish_green: bool = False,
        channel_send_enabled: bool = False,
    ) -> None:
        self.bot = bot
        self.service = service
        self.store = store
        self.owner_user_id = str(owner_user_id)
        self.owner_chat_id = str(owner_chat_id)
        self.channel_id = str(channel_id)
        self.auto_publish_green = auto_publish_green
        self.channel_send_enabled = channel_send_enabled

    async def create_post(self, request: EditorialRequest) -> dict[str, Any]:
        bundle = self.service.generate_bundle(request)
        item = self.store.create(bundle)

        if self.auto_publish_green and item.draft.risk is EditorialRisk.GREEN:
            if self.channel_send_enabled:
                item = await self._publish(item)
            else:
                item = self.store.set_status(item.publication_id, "ready")
                await self._send_review(item, note="Автопубликация GREEN готова, но канал-send выключен.")
        else:
            await self._send_review(item)

        return editorial_response_payload(item)

    async def handle_callback(self, update: dict[str, Any]) -> bool:
        callback = update.get("callback_query")
        if not isinstance(callback, dict):
            return False

        sender = callback.get("from") or {}
        if str(sender.get("id")) != self.owner_user_id:
            callback_id = str(callback.get("id") or "")
            if callback_id:
                await self.bot.answer_callback_query(
                    callback_query_id=callback_id,
                    text="Недостаточно прав.",
                )
            return True

        data = str(callback.get("data") or "")
        callback_id = str(callback.get("id") or "")
        action, publication_id = self._parse_callback(data)
        if not action or not publication_id:
            if callback_id:
                await self.bot.answer_callback_query(
                    callback_query_id=callback_id,
                    text="Неизвестная команда.",
                )
            return True

        try:
            if action == "publish":
                item = self.store.get(publication_id)
                if not self.channel_send_enabled:
                    self.store.set_status(publication_id, "ready")
                    message = "Готово к публикации, но отправка в канал выключена."
                else:
                    await self._publish(item)
                    message = "Опубликовано."

            elif action == "rewrite":
                previous = self.store.get(publication_id)
                replacement = self.service.generate_bundle(previous.request)
                item = self.store.replace_bundle(publication_id, replacement)
                await self._send_review(item, note="Текст и визуал перегенерированы.")
                message = "Новая версия готова."

            elif action == "image":
                item = self.store.get(publication_id)
                image_bytes = self.service.image_provider.generate(item.draft.image_prompt)
                item = self.store.replace_image(publication_id, image_bytes)
                await self._send_review(item, note="Сгенерирован новый визуал.")
                message = "Новый визуал готов."

            elif action == "reject":
                self.store.set_status(publication_id, "rejected")
                message = "Публикация отклонена."

            else:
                message = "Неизвестная команда."

        except KeyError:
            message = "Черновик не найден."
        except Exception:
            message = "Не удалось выполнить действие. Проверьте журнал Djafar."

        if callback_id:
            await self.bot.answer_callback_query(
                callback_query_id=callback_id,
                text=message,
            )
        return True

    async def _send_review(self, item: EditorialQueueItem, *, note: str | None = None) -> None:
        risk_label = {
            EditorialRisk.GREEN: "🟢 GREEN",
            EditorialRisk.YELLOW: "🟡 YELLOW",
            EditorialRisk.RED: "🔴 RED",
        }[item.draft.risk]
        preview_caption = f"{risk_label}\n{item.draft.title}\nID: {item.publication_id}"
        await self.bot.send_photo(
            chat_id=self.owner_chat_id,
            photo=item.image_bytes,
            filename=f"{item.publication_id}.jpg",
            caption=preview_caption[:1024],
        )

        text = item.draft.render_text()
        if note:
            text = f"{note}\n\n{text}"

        await self.bot.send_message(
            chat_id=self.owner_chat_id,
            text=text,
            reply_markup=self._review_keyboard(item.publication_id),
        )

    async def _publish(self, item: EditorialQueueItem) -> EditorialQueueItem:
        if not item.image_bytes:
            raise RuntimeError("publication visual is missing")

        self.store.set_status(item.publication_id, "publishing")
        try:
            await self.bot.send_photo(
                chat_id=self.channel_id,
                photo=item.image_bytes,
                filename=f"{item.publication_id}.jpg",
                caption=item.draft.title[:1024],
            )
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=item.draft.render_text(),
            )
        except Exception:
            self.store.set_status(item.publication_id, "error")
            raise

        return self.store.set_status(item.publication_id, "published")

    @staticmethod
    def _review_keyboard(publication_id: str) -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Опубликовать",
                        "callback_data": f"editorial:publish:{publication_id}",
                    },
                    {
                        "text": "❌ Отклонить",
                        "callback_data": f"editorial:reject:{publication_id}",
                    },
                ],
                [
                    {
                        "text": "✏️ Переписать",
                        "callback_data": f"editorial:rewrite:{publication_id}",
                    },
                    {
                        "text": "🖼 Новый визуал",
                        "callback_data": f"editorial:image:{publication_id}",
                    },
                ],
            ]
        }

    @staticmethod
    def _parse_callback(data: str) -> tuple[str | None, str | None]:
        parts = data.split(":", 2)
        if len(parts) != 3 or parts[0] != "editorial":
            return None, None
        action = parts[1]
        publication_id = parts[2]
        if action not in {"publish", "reject", "rewrite", "image"}:
            return None, None
        return action, publication_id
