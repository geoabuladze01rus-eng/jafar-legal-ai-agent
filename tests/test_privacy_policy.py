from __future__ import annotations

import pytest

from jafar.privacy_policy import ProviderPrivacyPolicy


def test_confidential_policy_allows_only_openai() -> None:
    policy = ProviderPrivacyPolicy()
    assert policy.allowed_providers(confidential=True) == ("openai",)


def test_non_confidential_policy_allows_configured_providers() -> None:
    policy = ProviderPrivacyPolicy()
    assert policy.allowed_providers(confidential=False) == (
        "openai",
        "gemini",
        "deepseek",
        "qwen",
        "kimi",
    )


def test_forbidden_provider_is_rejected() -> None:
    policy = ProviderPrivacyPolicy()
    with pytest.raises(PermissionError, match="forbidden"):
        policy.validate(confidential=True, requested=("openai", "deepseek"))


def test_explicit_permitted_allowlist_is_preserved() -> None:
    policy = ProviderPrivacyPolicy()
    assert policy.validate(
        confidential=False,
        requested=("openai", "deepseek"),
    ) == ("openai", "deepseek")
