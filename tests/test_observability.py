from jafar.observability import redact


def test_redact_removes_credentials_and_email() -> None:
    value = redact("Authorization: Bearer abc123 api_key=secret user=test@example.com")
    assert "abc123" not in value
    assert "secret" not in value
    assert "test@example.com" not in value
    assert "redacted" in value
