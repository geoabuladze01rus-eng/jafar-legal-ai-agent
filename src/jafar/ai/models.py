from dataclasses import dataclass


@dataclass(frozen=True)
class AIRequest:
    system_prompt: str
    user_prompt: str
    temperature: float = 0.0


@dataclass(frozen=True)
class AIResponse:
    text: str
    provider: str
    model: str


class AIProvider:
    """Provider boundary. Secrets and network clients stay outside the domain layer."""

    name = "unconfigured"
    model = "unconfigured"

    def complete(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError
