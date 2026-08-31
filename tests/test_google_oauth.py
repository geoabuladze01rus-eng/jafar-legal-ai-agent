from datetime import datetime, timedelta, timezone

from jafar.google_oauth import GoogleOAuthBroker, GoogleOAuthConfig, GoogleTokenSet, InMemoryGoogleTokenStore


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


def test_authorization_url_and_code_exchange_round_trip():
    broker = make_broker()
    url = broker.authorization_url("user-1")
    state = url.split("state=", 1)[1].split("&", 1)[0]
    from urllib.parse import unquote

    subject = broker.exchange_code(code="code", state=unquote(state))
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
    url = broker.authorization_url("user-1")
    state = url.split("state=", 1)[1].split("&", 1)[0]
    from urllib.parse import unquote

    state = unquote(state)
    try:
        broker.exchange_code(code="code", state=state + "x")
    except ValueError:
        pass
    else:
        raise AssertionError("tampered OAuth state must be rejected")
