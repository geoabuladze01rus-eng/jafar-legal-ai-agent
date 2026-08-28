from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderPrivacyPolicy:
    """Central policy deciding which AI providers may receive a request."""

    confidential_providers: tuple[str, ...] = ("openai",)
    non_confidential_providers: tuple[str, ...] = (
        "openai",
        "gemini",
        "deepseek",
        "qwen",
        "kimi",
    )

    def allowed_providers(self, *, confidential: bool) -> tuple[str, ...]:
        return self.confidential_providers if confidential else self.non_confidential_providers

    def validate(
        self,
        *,
        confidential: bool,
        requested: tuple[str, ...] | None = None,
    ) -> tuple[str, ...]:
        policy_allowed = set(self.allowed_providers(confidential=confidential))
        if requested is None:
            return tuple(policy_allowed)
        requested_set = set(requested)
        forbidden = requested_set - policy_allowed
        if forbidden:
            raise PermissionError(
                "Requested AI provider(s) are forbidden by confidentiality policy: "
                + ", ".join(sorted(forbidden))
            )
        return tuple(requested)
