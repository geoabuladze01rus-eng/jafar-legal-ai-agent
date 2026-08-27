from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class GmailSetupRequired(RuntimeError):
    """Raised when the one-time local Gmail authorization has not been completed."""


class GmailReauthorizationRequired(RuntimeError):
    """Raised when saved Gmail authorization can no longer be refreshed safely."""


class GmailCredentialStoreError(RuntimeError):
    """Raised when the protected local credential store is unavailable."""


class GmailCredentialStore(Protocol):
    def load(self) -> str | None: ...

    def save(self, serialized_credentials: str) -> None: ...

    def delete(self) -> None: ...


class KeychainGmailCredentialStore:
    """Store the OAuth credential bundle in the user's protected local keychain.

    The repository never receives a token file. On macOS, ``keyring`` routes this
    generic password entry to Keychain. Other supported local keyring backends can
    provide an equivalent protected store for development and tests.
    """

    SERVICE = "ru.jafar.legal-ai.gmail-oauth"
    ACCOUNT = "gmail-readonly"

    @staticmethod
    def _keyring():
        try:
            import keyring

            backend = keyring.get_keyring()
        except Exception:  # noqa: BLE001 - provider details may contain secrets.
            raise GmailCredentialStoreError(
                "Локальное защищённое хранилище Gmail недоступно."
            ) from None
        if sys.platform == "darwin" and not type(backend).__module__.startswith(
            "keyring.backends.macOS"
        ):
            raise GmailCredentialStoreError(
                "Gmail OAuth не будет сохранён: macOS Keychain backend не активен."
            )
        return keyring

    def load(self) -> str | None:
        try:
            keyring = self._keyring()
            return keyring.get_password(self.SERVICE, self.ACCOUNT)
        except Exception:  # noqa: BLE001 - provider details may contain secrets.
            raise GmailCredentialStoreError(
                "Не удалось прочитать Gmail OAuth из локального защищённого хранилища."
            ) from None

    def save(self, serialized_credentials: str) -> None:
        if not serialized_credentials.strip():
            raise ValueError("Serialized Gmail credentials must not be empty")
        try:
            keyring = self._keyring()
            keyring.set_password(self.SERVICE, self.ACCOUNT, serialized_credentials)
        except Exception:  # noqa: BLE001 - provider details may contain secrets.
            raise GmailCredentialStoreError(
                "Не удалось сохранить Gmail OAuth в локальном защищённом хранилище."
            ) from None

    def delete(self) -> None:
        try:
            keyring = self._keyring()
            try:
                keyring.delete_password(self.SERVICE, self.ACCOUNT)
            except keyring.errors.PasswordDeleteError:
                return
        except Exception:  # noqa: BLE001 - provider details may contain secrets.
            raise GmailCredentialStoreError(
                "Не удалось удалить Gmail OAuth из локального защищённого хранилища."
            ) from None


class GmailCredentialManager:
    """Load and refresh one exact-scope OAuth grant without exposing its contents."""

    def __init__(
        self,
        store: GmailCredentialStore,
        *,
        request_factory: Callable[[], Any] = Request,
    ) -> None:
        self.store = store
        self.request_factory = request_factory

    def load_valid_credentials(self) -> Credentials:
        serialized = self.store.load()
        if serialized is None:
            raise GmailSetupRequired(
                "Gmail ещё не подключён. Нужна однократная локальная OAuth-настройка."
            )

        try:
            info = json.loads(serialized)
        except (TypeError, json.JSONDecodeError):
            raise GmailReauthorizationRequired(
                "Сохранённая Gmail-авторизация повреждена; подключите Gmail заново."
            ) from None
        if (
            not isinstance(info, dict)
            or self._scopes(info.get("scopes")) != {GMAIL_READONLY_SCOPE}
            or info.get("token_uri") != GOOGLE_TOKEN_URI
        ):
            raise GmailReauthorizationRequired(
                "Сохранённая Gmail-авторизация не ограничена gmail.readonly; подключите Gmail заново."
            )

        try:
            credentials = Credentials.from_authorized_user_info(
                info,
                scopes=[GMAIL_READONLY_SCOPE],
            )
        except (TypeError, ValueError):
            raise GmailReauthorizationRequired(
                "Сохранённая Gmail-авторизация недействительна; подключите Gmail заново."
            ) from None

        if credentials.valid:
            return credentials
        if not credentials.refresh_token:
            raise GmailReauthorizationRequired(
                "Gmail-сессия истекла и не может быть обновлена; подключите Gmail заново."
            )

        try:
            credentials.refresh(self.request_factory())
        except Exception:  # noqa: BLE001 - never surface token endpoint details.
            raise GmailReauthorizationRequired(
                "Google отклонил обновление Gmail-сессии; подключите Gmail заново."
            ) from None
        if not credentials.valid:
            raise GmailReauthorizationRequired(
                "Gmail-сессия не обновилась; подключите Gmail заново."
            )
        if self._credential_scopes(credentials) != {GMAIL_READONLY_SCOPE}:
            raise GmailReauthorizationRequired(
                "Обновлённая Gmail-авторизация имеет неверные права; подключите Gmail заново."
            )
        self.store.save(credentials.to_json())
        return credentials

    @staticmethod
    def _scopes(raw_scopes: object) -> set[str]:
        if isinstance(raw_scopes, str):
            return {item for item in raw_scopes.split() if item}
        if isinstance(raw_scopes, list):
            return {str(item) for item in raw_scopes if item}
        return set()

    @classmethod
    def _credential_scopes(cls, credentials: Credentials) -> set[str]:
        return cls._scopes(credentials.granted_scopes or credentials.scopes)


def _validate_desktop_client_payload(payload: object) -> None:
    if not isinstance(payload, dict) or not isinstance(payload.get("installed"), dict):
        raise GmailSetupRequired("Нужен OAuth client типа Desktop app, а не Web application.")
    installed = payload["installed"]
    if (
        not isinstance(installed.get("client_id"), str)
        or not installed["client_id"].strip()
        or not isinstance(installed.get("client_secret"), str)
        or not installed["client_secret"].strip()
        or installed.get("auth_uri") != GOOGLE_AUTH_URI
        or installed.get("token_uri") != GOOGLE_TOKEN_URI
    ):
        raise GmailSetupRequired(
            "OAuth JSON Desktop app не содержит ожидаемые Google OAuth endpoints."
        )
    redirects = installed.get("redirect_uris")
    if not isinstance(redirects, list) or not redirects:
        raise GmailSetupRequired("OAuth JSON не разрешает безопасный loopback redirect.")
    for redirect in redirects:
        if not isinstance(redirect, str):
            raise GmailSetupRequired("OAuth JSON содержит небезопасный redirect URI.")
        parsed = urlsplit(redirect)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise GmailSetupRequired("OAuth JSON содержит небезопасный redirect URI.")


def authorize_gmail_desktop_app(
    client_secrets_path: str | Path,
    store: GmailCredentialStore,
) -> None:
    """Run Google's installed-app loopback flow and persist only in the keychain."""

    path = Path(client_secrets_path).expanduser()
    if not path.is_file():
        raise GmailSetupRequired("Не найден локальный JSON-файл OAuth Desktop app.")
    try:
        if path.stat().st_size > 128 * 1024:
            raise GmailSetupRequired("OAuth JSON выглядит некорректно: файл слишком большой.")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except GmailSetupRequired:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise GmailSetupRequired("Не удалось прочитать OAuth JSON Desktop app.") from None
    _validate_desktop_client_payload(payload)

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(path),
            scopes=[GMAIL_READONLY_SCOPE],
        )
        credentials = flow.run_local_server(
            host="127.0.0.1",
            port=0,
            open_browser=True,
            access_type="offline",
            prompt="consent",
            authorization_prompt_message=(
                "Откроется системный браузер для локального Gmail read-only доступа."
            ),
            success_message=(
                "Gmail подключён к локальному Jafar в режиме только чтения. Это окно можно закрыть."
            ),
        )
    except Exception:  # noqa: BLE001 - never surface OAuth response details.
        raise GmailSetupRequired(
            "Локальная Gmail OAuth-настройка не завершена. Повторите её после проверки клиента."
        ) from None

    granted = set(credentials.granted_scopes or credentials.scopes or ())
    if granted != {GMAIL_READONLY_SCOPE}:
        raise GmailReauthorizationRequired(
            "Google вернул неожиданный набор разрешений; авторизация не сохранена."
        )
    if not credentials.refresh_token:
        raise GmailReauthorizationRequired(
            "Google не вернул локальный refresh token; авторизация не сохранена."
        )
    store.save(credentials.to_json())
