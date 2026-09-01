from __future__ import annotations

import pytest

from jafar.privacy_policy import ProviderPrivacyPolicy


def test_confidential_policy_allows_local_ollama_and_openai_fallback() -> None:
    policy = ProviderPrivacyPolicy()
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
    policy = ProviderPrivacyPolicy()
    with pytest.raises(PermissionError, match="forbidden"):
        policy.validate(confidential=True, requested=("ollama", "deepseek"))


def test_explicit_permitted_allowlist_is_preserved() -> None:
    policy = ProviderPrivacyPolicy()
    assert policy.validate(
        confidential=False,
        requested=("ollama", "openai", "deepseek"),
    ) == ("ollama", "openai", "deepseek")


def test_default_validation_preserves_policy_order() -> None:
    policy = ProviderPrivacyPolicy()
    assert policy.validate(confidential=True) == ("ollama", "openai")
