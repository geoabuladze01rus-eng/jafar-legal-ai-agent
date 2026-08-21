from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets


@dataclass(frozen=True)
class Session:
    session_id: str
    user_id: str
    device_id: str
    issued_at: datetime
    expires_at: datetime


class SessionManager:
    """Minimal signed-session boundary. Secrets must come from runtime configuration."""

    def __init__(self, secret: str, ttl: timedelta = timedelta(hours=12)) -> None:
        if not secret:
            raise ValueError("session secret is required")
        self._secret = secret.encode()
        self._ttl = ttl

    def issue(self, user_id: str, device_id: str) -> Session:
        now = datetime.now(timezone.utc)
        return Session(secrets.token_urlsafe(24), user_id, device_id, now, now + self._ttl)

    def sign(self, session: Session) -> str:
        payload = f"{session.session_id}.{session.user_id}.{session.device_id}.{int(session.expires_at.timestamp())}"
        signature = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"
