import asyncio

import httpx

from jafar.telegram_adapter import TelegramApiError, TelegramBotApiSender


def test_send_text_uses_telegram_send_message():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 11, "chat": {"id": 42}}})

    async def run():
        sender = TelegramBotApiSender("test-token")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            original = httpx.AsyncClient
            httpx.AsyncClient = lambda **kwargs: client
            try:
                return await sender.send_text(chat_id="@iznanka_ugolovki", text="hello")
            finally:
                httpx.AsyncClient = original

    result = asyncio.run(run())
    assert result.message_id == 11
    assert requests[0].url.path.endswith("/sendMessage")


def test_send_photo_and_video_use_correct_methods():
    methods = []

    async def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.url.path)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 12, "chat": {"id": 42}}})

    async def run():
        sender = TelegramBotApiSender("test-token")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            original = httpx.AsyncClient
            httpx.AsyncClient = lambda **kwargs: client
            try:
                await sender.send_media(chat_id="@iznanka_ugolovki", media_type="photo", media_url="https://example.test/a.jpg", caption="photo")
                await sender.send_media(chat_id="@iznanka_ugolovki", media_type="video", media_url="https://example.test/a.mp4", caption="video")
            finally:
                httpx.AsyncClient = original

    asyncio.run(run())
    assert methods == ["/bottest-token/sendPhoto", "/bottest-token/sendVideo"]


def test_telegram_api_error_is_raised():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "blocked"})

    async def run():
        sender = TelegramBotApiSender("test-token")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            original = httpx.AsyncClient
            httpx.AsyncClient = lambda **kwargs: client
            try:
                await sender.send_text(chat_id="@iznanka_ugolovki", text="hello")
            finally:
                httpx.AsyncClient = original

    try:
        asyncio.run(run())
    except TelegramApiError as exc:
        assert str(exc) == "blocked"
    else:
        raise AssertionError("TelegramApiError expected")
