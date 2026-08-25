from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class DeviceCodeChallenge:
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class MicrosoftDeviceCodeAuth:
    """Acquire a short-lived delegated Graph token without persisting credentials."""

    def __init__(
        self,
        client_id: str,
        *,
        tenant: str = "consumers",
        client: httpx.Client | None = None,
    ) -> None:
        normalized_client_id = client_id.strip()
        if not normalized_client_id:
            raise ValueError("Microsoft public-client application ID is required")
        normalized_tenant = tenant.strip() or "consumers"
        self._client_id = normalized_client_id
        self._tenant = normalized_tenant
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=f"https://login.microsoftonline.com/{normalized_tenant}/oauth2/v2.0",
            timeout=15.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def request_device_code(self, *, scope: str = "https://graph.microsoft.com/Mail.Read") -> DeviceCodeChallenge:
        response = self._client.post(
            "/devicecode",
            data={"client_id": self._client_id, "scope": scope},
        )
        self._raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("Microsoft device-code response must be a JSON object")

        try:
            device_code = str(payload["device_code"])
            user_code = str(payload["user_code"])
            verification_uri = str(payload["verification_uri"])
            expires_in = int(payload["expires_in"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Microsoft device-code response is missing required fields") from exc

        interval = int(payload.get("interval") or 5)
        return DeviceCodeChallenge(
            device_code=device_code,
            user_code=user_code,
            verification_uri=verification_uri,
            expires_in=expires_in,
            interval=max(interval, 1),
        )

    def poll_access_token(
        self,
        challenge: DeviceCodeChallenge,
        *,
        scope: str = "https://graph.microsoft.com/Mail.Read",
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> str:
        deadline = monotonic() + challenge.expires_in
        interval = challenge.interval

        while monotonic() < deadline:
            response = self._client.post(
                "/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": self._client_id,
                    "device_code": challenge.device_code,
                    "scope": scope,
                },
            )
            payload = response.json()
            if response.is_success:
                if not isinstance(payload, dict):
                    raise TypeError("Microsoft token response must be a JSON object")
                access_token = str(payload.get("access_token") or "").strip()
                if not access_token:
                    raise ValueError("Microsoft token response did not contain an access token")
                return access_token

            error = payload.get("error") if isinstance(payload, dict) else None
            if error == "authorization_pending":
                sleeper(interval)
                continue
            if error == "slow_down":
                interval += 5
                sleeper(interval)
                continue
            if error in {"authorization_declined", "expired_token", "bad_verification_code"}:
                raise RuntimeError(f"Microsoft device authorization failed: {error}")

            raise RuntimeError(f"Microsoft device authorization failed with HTTP {response.status_code}")

        raise TimeoutError("Microsoft device authorization expired before sign-in completed")

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        raise RuntimeError(f"Microsoft identity request failed with HTTP {response.status_code}")
