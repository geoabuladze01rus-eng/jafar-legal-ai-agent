from jafar.api_auth import configured_api_token, validate_bearer_value


def test_auth_disabled_when_token_is_not_configured(monkeypatch):
    monkeypatch.delenv("JAFAR_API_BEARER_TOKEN", raising=False)
    assert configured_api_token() is None
    assert validate_bearer_value(None) is True


def test_auth_accepts_matching_bearer_token(monkeypatch):
    monkeypatch.setenv("JAFAR_API_BEARER_TOKEN", "secret-token")
    assert validate_bearer_value("Bearer secret-token") is True


def test_auth_rejects_missing_or_wrong_token(monkeypatch):
    monkeypatch.setenv("JAFAR_API_BEARER_TOKEN", "secret-token")
    assert validate_bearer_value(None) is False
    assert validate_bearer_value("Basic secret-token") is False
    assert validate_bearer_value("Bearer wrong-token") is False
