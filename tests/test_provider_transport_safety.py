from __future__ import annotations

import io

import pytest

from jafar.provider_transport_safety import (
    read_json_response_limited,
    validate_prompt_transport,
    validate_provider_endpoint,
)


def test_provider_endpoints_require_https_and_reviewed_hosts() -> None:
    assert (
        validate_provider_endpoint("https://api.openai.com/v1/responses")
        == "https://api.openai.com/v1/responses"
    )
    assert (
        validate_provider_endpoint("https://api.deepseek.com/chat/completions")
        == "https://api.deepseek.com/chat/completions"
    )

    with pytest.raises(RuntimeError, match="https_required"):
        validate_provider_endpoint("http://api.openai.com/v1/responses")
    with pytest.raises(RuntimeError, match="host_not_trusted"):
        validate_provider_endpoint("https://attacker.example/v1/responses")
    with pytest.raises(RuntimeError, match="userinfo_forbidden"):
        validate_provider_endpoint("https://user:pass@api.openai.com/v1/responses")


def test_explicit_custom_host_is_opt_in_and_ip_literals_stay_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("AI_TRUSTED_PROVIDER_HOSTS", "models.company.example,127.0.0.1")

    assert (
        validate_provider_endpoint("https://models.company.example/v1/chat")
        == "https://models.company.example/v1/chat"
    )
    with pytest.raises(RuntimeError, match="private_address_forbidden"):
        validate_provider_endpoint("https://127.0.0.1/v1/chat")


def test_prompt_transport_has_a_hard_utf8_size_limit() -> None:
    validate_prompt_transport("короткий запрос", max_bytes=100)

    with pytest.raises(RuntimeError, match="provider_prompt_too_large"):
        validate_prompt_transport("ю" * 100, max_bytes=100)


def test_provider_response_is_bounded_and_must_be_json_object() -> None:
    assert read_json_response_limited(io.BytesIO(b'{"ok":true}'), max_bytes=100) == {"ok": True}

    with pytest.raises(RuntimeError, match="provider_response_too_large"):
        read_json_response_limited(io.BytesIO(b"{" + b"x" * 100 + b"}"), max_bytes=50)
    with pytest.raises(RuntimeError, match="provider_response_invalid_json"):
        read_json_response_limited(io.BytesIO(b"not-json"), max_bytes=100)
    with pytest.raises(RuntimeError, match="provider_response_must_be_object"):
        read_json_response_limited(io.BytesIO(b"[]"), max_bytes=100)
