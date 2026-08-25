from __future__ import annotations

import httpx

from jafar.microsoft_device_auth import MicrosoftDeviceCodeAuth


def test_device_code_auth_acquires_token_without_persisting_it():
    calls: list[str] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/oauth2/v2.0/devicecode":
            return httpx.Response(
                200,
                json={
                    "device_code": "device-code",
                    "user_code": "ABCD-EFGH",
                    "verification_uri": "https://microsoft.com/devicelogin",
                    "expires_in": 600,
                    "interval": 1,
                },
            )
        if request.url.path == "/oauth2/v2.0/token" and calls.count("/oauth2/v2.0/token") == 1:
            return httpx.Response(400, json={"error": "authorization_pending"})
        if request.url.path == "/oauth2/v2.0/token":
            return httpx.Response(200, json={"access_token": "short-lived-token"})
        raise AssertionError(f"Unexpected request: {request.url}")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        transport=transport,
        base_url="https://login.microsoftonline.com/consumers",
    )
    auth = MicrosoftDeviceCodeAuth("client-id", client=http_client)

    challenge = auth.request_device_code()
    token = auth.poll_access_token(
        challenge,
        sleeper=sleeps.append,
        monotonic=lambda: 0.0,
    )

    assert challenge.user_code == "ABCD-EFGH"
    assert token == "short-lived-token"
    assert sleeps == [1]


def test_device_code_auth_does_not_leak_provider_error_description():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": "authorization_declined",
                "error_description": "sensitive provider detail",
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        transport=transport,
        base_url="https://login.microsoftonline.com/consumers",
    )
    auth = MicrosoftDeviceCodeAuth("client-id", client=http_client)

    challenge = type("Challenge", (), {
        "device_code": "device-code",
        "expires_in": 600,
        "interval": 1,
    })()

    try:
        auth.poll_access_token(challenge, sleeper=lambda _: None, monotonic=lambda: 0.0)
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected authorization failure")

    assert "authorization_declined" in message
    assert "sensitive provider detail" not in message
