from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from jafar.google_oauth import (
    GoogleOAuthBroker,
    GoogleOAuthConfig,
    GoogleTokenSet,
    InMemoryGoogleTokenStore,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self):
        self.calls = []

    def post(self, url, data):
        self.calls.append((url, data))
        if data["grant_type"] == "authorization_code":
            return FakeResponse({"access_token": "a1", "refresh_token": "r1", "expires_in": 3600})
        return FakeResponse({"access_token": "a2", "expires_in": 3600})


def make_broker():
    config = GoogleOAuthConfig("cid", "secret", "https://example.test/callback", "state-secret")
    return GoogleOAuthBroker(config, InMemoryGoogleTokenStore(), client=FakeClient())


def extract_state(url: str) -> str:
    return parse_qs(urlparse(url).query)["state"][0]


def test_authorization_url_and_code_exchange_round_trip():
    broker = make_broker()
    state = extract_state(broker.authorization_url("user-1"))

    subject = broker.exchange_code(code="code", state=state)
    assert subject == "user-1"
    assert broker.access_token("user-1") == "a1"


def test_refreshes_expiring_access_token():
    broker = make_broker()
    broker.token_store.save(
        "user-1",
        GoogleTokenSet(
            access_token="expired",
            refresh_token="r1",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=5),
        ),
    )
    assert broker.access_token("user-1") == "a2"
    assert broker.token_store.load("user-1").refresh_token == "r1"


def test_rejects_tampered_state():
    broker = make_broker()
    state = extract_state(broker.authorization_url("user-1"))

    with pytest.raises(ValueError, match="Invalid, expired, or already used"):
        broker.exchange_code(code="code", state=state + "x")


def test_oauth_state_can_be_consumed_only_once():
    broker = make_broker()
    state = extract_state(broker.authorization_url("user-1"))

    assert broker.exchange_code(code="first-code", state=state) == "user-1"
    assert len(broker.client.calls) == 1

    with pytest.raises(ValueError, match="already used"):
        broker.exchange_code(code="replayed-code", state=state)

    assert len(broker.client.calls) == 1
