import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from jafar.telegram_http import router


@pytest.mark.asyncio
async def test_webhook_routes_sensitive_message_to_review(monkeypatch):
    from jafar import config
    monkeypatch.setattr(config.settings, "telegram_webhook_secret", "secret")

    app = FastAPI()
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
            json={"message": {"text": "Что делать после задержания?"}},
        )

    assert response.status_code == 200
    assert response.json()["action"] == "review"


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_secret(monkeypatch):
    from jafar import config
    monkeypatch.setattr(config.settings, "telegram_webhook_secret", "secret")

    app = FastAPI()
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            json={"message": {"text": "hello"}},
        )

    assert response.status_code == 403
