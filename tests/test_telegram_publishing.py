from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from jafar.telegram_publishing import TelegramPublisher
from jafar.telegram_runtime import TelegramBotHttpClient


class FakeTelegramClient:
    def __init__(self) -> None:
        self.photos: list[dict[str, object]] = []
        self.videos: list[dict[str, object]] = []
        self.messages: list[dict[str, object]] = []

    async def send_photo(self, **kwargs: object) -> dict[str, int]:
        self.photos.append(kwargs)
        return {"message_id": 10}

    async def send_message(self, **kwargs: object) -> dict[str, int]:
        self.messages.append(kwargs)
        return {"message_id": 10 + len(self.messages)}

    async def send_video(self, **kwargs: object) -> dict[str, int]:
        self.videos.append(kwargs)
        return {"message_id": 20}


MINIMAL_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2"


def test_photo_with_long_caption_sends_photo_then_bounded_text_and_rechecks_allowlist() -> None:
    client = FakeTelegramClient()
    allow_calls: list[str] = []

    def allow(chat_id: int | str) -> str:
        allow_calls.append(str(chat_id))
        return str(chat_id)

    publisher = TelegramPublisher(lambda: client, allow)
    result = asyncio.run(
        publisher.publish(
            chat_id="-1001",
            text="x" * 5000,
            photo_bytes=b"\x89PNG\r\n\x1a\nimage",
            filename="test.png",
        )
    )

    assert result.mode == "photo_then_text"
    assert client.photos[0]["caption"] == ""
    assert [len(str(message["text"])) for message in client.messages] == [4096, 904]
    assert len(allow_calls) == 3


def test_publisher_refuses_destination_that_is_no_longer_allowlisted() -> None:
    client = FakeTelegramClient()

    def blocked(_chat_id: int | str) -> str:
        raise PermissionError("Telegram destination is not allowlisted")

    publisher = TelegramPublisher(lambda: client, blocked)
    with pytest.raises(PermissionError, match="allowlisted"):
        asyncio.run(publisher.publish(chat_id="-1001", text="blocked"))
    assert client.messages == []


def test_mp4_with_long_caption_sends_video_then_text_and_rechecks_allowlist() -> None:
    client = FakeTelegramClient()
    allow_calls: list[str] = []

    def allow(chat_id: int | str) -> str:
        allow_calls.append(str(chat_id))
        return str(chat_id)

    result = asyncio.run(
        TelegramPublisher(lambda: client, allow).publish(
            chat_id="-1001", text="x" * 5000, video_bytes=MINIMAL_MP4, filename="safe.mp4"
        )
    )

    assert result.mode == "video_then_text"
    assert result.video_message_id == 20
    assert client.videos == [
        {
            "chat_id": "-1001",
            "caption": "",
            "video_url": None,
            "video_bytes": MINIMAL_MP4,
            "filename": "safe.mp4",
        }
    ]
    assert [len(str(message["text"])) for message in client.messages] == [4096, 904]
    assert len(allow_calls) == 3


@pytest.mark.parametrize(
    ("video", "filename", "maximum"),
    [
        (b"", "safe.mp4", 20 * 1024 * 1024),
        (b"not-an-mp4", "safe.mp4", 20 * 1024 * 1024),
        (MINIMAL_MP4, "unsafe.png", 20 * 1024 * 1024),
        (MINIMAL_MP4, "safe.mp4", 1),
    ],
)
def test_video_validation_rejects_empty_fake_wrong_filename_and_oversize(
    video: bytes, filename: str, maximum: int
) -> None:
    with pytest.raises(ValueError):
        asyncio.run(
            TelegramPublisher(lambda: FakeTelegramClient(), lambda chat: str(chat)).publish(
                chat_id="-1001",
                text="test",
                video_bytes=video,
                filename=filename,
                max_video_bytes=maximum,
            )
        )


def test_video_and_photo_or_multiple_video_sources_are_rejected() -> None:
    publisher = TelegramPublisher(lambda: FakeTelegramClient(), lambda chat: str(chat))
    with pytest.raises(ValueError, match="photo or video"):
        asyncio.run(
            publisher.publish(
                chat_id="-1001",
                text="test",
                photo_bytes=b"\x89PNG\r\n\x1a\nimage",
                video_bytes=MINIMAL_MP4,
            )
        )
    with pytest.raises(ValueError, match="only one"):
        asyncio.run(
            publisher.publish(
                chat_id="-1001",
                text="test",
                video_bytes=MINIMAL_MP4,
                video_url="https://example.test/video.mp4",
                filename="safe.mp4",
            )
        )


def test_send_video_uses_same_safe_http_path(monkeypatch) -> None:
    sent: dict[str, object] = {}

    async def fake_post(self, method: str, **kwargs: object) -> dict[str, object]:
        sent["method"] = method
        sent.update(kwargs)
        return {"message_id": 21}

    monkeypatch.setattr(TelegramBotHttpClient, "_post", fake_post)
    result = asyncio.run(
        TelegramBotHttpClient("very-secret-token").send_video(
            chat_id="-1001", video_bytes=MINIMAL_MP4, filename="safe.mp4", caption="caption"
        )
    )
    assert result["message_id"] == 21
    assert sent["method"] == "sendVideo"
    assert sent["files"] == {"video": ("safe.mp4", MINIMAL_MP4, "video/mp4")}


def test_poll_payload_and_telegram_error_are_safely_normalized(monkeypatch) -> None:
    sent: dict[str, object] = {}

    async def fake_post(self, method: str, **kwargs: object) -> dict[str, object]:
        sent["method"] = method
        sent.update(kwargs)
        return {"message_id": 19, "poll": {"id": "poll-1"}}

    monkeypatch.setattr(TelegramBotHttpClient, "_post", fake_post)
    result = asyncio.run(
        TelegramBotHttpClient("very-secret-token").send_poll(
            chat_id="-1001",
            poll={
                "question": "Question",
                "options": ["A", "B"],
                "is_anonymous": False,
                "allows_multiple_answers": False,
                "type": "quiz",
                "correct_option_ids": [1],
                "explanation": "Because.",
                "open_period": 60,
            },
        )
    )
    assert result["message_id"] == 19
    assert sent["method"] == "sendPoll"
    assert json.loads(str(sent["data"]["options"])) == [{"text": "A"}, {"text": "B"}]
    monkeypatch.undo()

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"ok": False, "description": "very-secret-token confidential post body"},
        )
    )
    real_async_client = httpx.AsyncClient

    class ClientWithMockTransport:
        def __init__(self, **_kwargs: object) -> None:
            self.client = real_async_client(transport=transport)

        async def __aenter__(self) -> httpx.AsyncClient:
            return self.client

        async def __aexit__(self, *_args: object) -> None:
            await self.client.aclose()

    monkeypatch.setattr("jafar.telegram_runtime.httpx.AsyncClient", ClientWithMockTransport)
    with pytest.raises(RuntimeError, match="API request failed") as error:
        asyncio.run(TelegramBotHttpClient("very-secret-token").send_message(chat_id="-1001", text="secret"))
    assert "very-secret-token" not in str(error.value)
    assert "confidential post body" not in str(error.value)
