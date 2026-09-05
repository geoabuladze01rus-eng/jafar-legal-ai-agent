from __future__ import annotations

import pytest

from jafar.privacy_policy import ProviderPrivacyPolicy, confidential_cloud_fallback_enabled


def test_default_confidential_policy_is_local_only() -> None:
    policy = ProviderPrivacyPolicy()
    assert policy.allowed_providers(confidential=True) == ("ollama",)


def test_runtime_can_be_configured_local_only() -> None:
    policy = ProviderPrivacyPolicy(confidential_providers=("ollama",))
    assert policy.allowed_providers(confidential=True) == ("ollama",)


def test_runtime_can_explicitly_enable_confidential_cloud_fallback() -> None:
    policy = ProviderPrivacyPolicy(confidential_providers=("ollama", "openai"))
    assert policy.allowed_providers(confidential=True) == ("ollama", "openai")


def test_non_confidential_policy_allows_configured_providers() -> None:
    policy = ProviderPrivacyPolicy()
    assert policy.allowed_providers(confidential=False) == (
        "ollama",
        "openai",
        "gemini",
        "deepseek",
    )


def test_forbidden_provider_is_rejected() -> None:
    policy = ProviderPrivacyPolicy(confidential_providers=("ollama",))
    with pytest.raises(PermissionError, match="forbidden"):
        policy.validate(confidential=True, requested=("ollama", "openai"))


def test_explicit_permitted_allowlist_is_preserved() -> None:
    policy = ProviderPrivacyPolicy()
    assert policy.validate(
        confidential=False,
        requested=("ollama", "openai", "deepseek"),
    ) == ("ollama", "openai", "deepseek")


def test_validation_preserves_configured_provider_order() -> None:
    policy = ProviderPrivacyPolicy(confidential_providers=("ollama", "openai"))
    assert policy.validate(confidential=True) == ("ollama", "openai")


@pytest.mark.parametrize("value", [None, "", "false", "FALSE", "1", "yes"])
def test_confidential_cloud_fallback_requires_explicit_true(monkeypatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv("CONFIDENTIAL_CLOUD_FALLBACK", raising=False)
    else:
        monkeypatch.setenv("CONFIDENTIAL_CLOUD_FALLBACK", value)
    assert confidential_cloud_fallback_enabled() is False


def test_confidential_cloud_fallback_accepts_explicit_true(monkeypatch) -> None:
    monkeypatch.setenv("CONFIDENTIAL_CLOUD_FALLBACK", "true")
    assert confidential_cloud_fallback_enabled() is True
