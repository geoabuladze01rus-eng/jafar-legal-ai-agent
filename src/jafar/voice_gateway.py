from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class VoiceCommand:
    device: str
    text: str
    request_id: str
    authenticated: bool = False


@dataclass(frozen=True, slots=True)
class VoiceResult:
    status: str
    response_text: str
    action: str | None = None
    metadata: dict[str, Any] | None = None


class VoiceCommandGateway:
    """Apple voice command boundary with authentication and approval gates."""

    ALLOWED_DEVICES = frozenset({"iphone", "ipad", "mac"})

    def __init__(self, command_handler: Callable[[str], str]) -> None:
        self.command_handler = command_handler

    def handle(self, command: VoiceCommand, *, approved: bool = False) -> VoiceResult:
        if command.device.lower() not in self.ALLOWED_DEVICES:
            return VoiceResult("rejected", "Устройство не разрешено.")
        if not command.authenticated:
            return VoiceResult("unauthorized", "Требуется авторизация.")
        text = command.text.strip()
        if not text:
            return VoiceResult("empty", "Я не услышал команду.")
        if not approved:
            return VoiceResult("approval_required", "Команда подготовлена и ожидает подтверждения.", metadata={"command": text})
        try:
            result = self.command_handler(text)
            return VoiceResult("completed", result, action=text)
        except Exception as exc:  # noqa: BLE001 - voice boundary normalizes handler failures
            return VoiceResult("error", "Не удалось выполнить команду.", metadata={"error": str(exc)})
