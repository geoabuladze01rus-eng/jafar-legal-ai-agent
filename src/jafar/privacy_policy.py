from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderPrivacyPolicy:
    """Central policy deciding which AI providers may receive a request.

    Ollama is treated as a local provider: confidential text may stay on the user's
    machine. OpenAI remains an explicitly permitted confidential cloud fallback.
    """

    confidential_providers: tuple[str, ...] = ("ollama", "openai")
    non_confidential_providers: tuple[str, ...] = (
        "ollama",
        "openai",
        "gemini",
        "deepseek",
    )

    def allowed_providers(self, *, confidential: bool) -> tuple[str, ...]:
        return self.confidential_providers if confidential else self.non_confidential_providers

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
