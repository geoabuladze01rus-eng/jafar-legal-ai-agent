from __future__ import annotations

import json
from urllib.request import Request, urlopen

from .recovery_incident import RecoveryIncident


class TelegramAlertSink:
    """Minimal Telegram Bot API sink; credentials are supplied only at runtime."""

    def __init__(self, *, bot_token: str, chat_id: str, timeout_seconds: int = 10) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds

    def send(self, *, incident: RecoveryIncident) -> None:
        text = (
            f"🚨 Jafar recovery incident\n"
            f"Severity: {incident.severity}\n"
            f"Type: {incident.incident_type}\n"
            f"Details: {incident.details}\n"
            f"Incident ID: {incident.incident_id}"
        )
        payload = json.dumps({"chat_id": self.chat_id, "text": text}).encode("utf-8")
        request = Request(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Telegram alert failed with HTTP {response.status}")
