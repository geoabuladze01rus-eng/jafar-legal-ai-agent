from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderPrivacyPolicy:
    """Central policy deciding which AI providers may receive a request.

    Confidential requests stay on local Ollama by default. Cloud fallback must be
    enabled explicitly so an unavailable local model cannot silently cause data egress.
    """

    allow_confidential_cloud_fallback: bool = False
    confidential_local_providers: tuple[str, ...] = ("ollama",)
    confidential_cloud_providers: tuple[str, ...] = ("openai",)
    non_confidential_providers: tuple[str, ...] = (
        "ollama",
        "openai",
        "gemini",
        "deepseek",
    )

    def allowed_providers(self, *, confidential: bool) -> tuple[str, ...]:
        if not confidential:
            return self.non_confidential_providers
        if self.allow_confidential_cloud_fallback:
            return self.confidential_local_providers + self.confidential_cloud_providers
        return self.confidential_local_providers

    def validate(self, *, confidential: bool, requested: tuple[str, ...] | None = None) -> tuple[str, ...]:
        policy_allowed = self.allowed_providers(confidential=confidential)
        if requested is None:
            return policy_allowed

        allowed_set = set(policy_allowed)
        requested_set = set(requested)
        forbidden = requested_set - allowed_set
        if forbidden:
            raise PermissionError(
                "Requested AI provider(s) are forbidden by confidentiality policy: "
                + ", ".join(sorted(forbidden))
            )
        return tuple(requested)
