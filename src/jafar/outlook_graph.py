from __future__ import annotations

import hashlib
from typing import Self
from urllib.parse import quote

import httpx


class MicrosoftGraphOutlookClient:
    """Read-only Microsoft Graph adapter for Jafar's Outlook provider contract.

    The access token is supplied by the caller and is never persisted by this
    class. Supported attachment bytes are kept in memory only long enough for
    the downstream document pipeline to materialize them.
    """

    def __init__(
        self,
        access_token: str,
        *,
        client: httpx.Client | None = None,
        base_url: str = "https://graph.microsoft.com/v1.0",
    ) -> None:
        token = access_token.strip()
        if not token:
            raise ValueError("Microsoft Graph access token is required")
        self._access_token = token
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=base_url, timeout=15.0)
        self._attachment_cache: dict[str, bytes] = {}

    def close(self) -> None:
        self._attachment_cache.clear()
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def list_messages(self, *, limit: int = 25) -> list[dict]:
        if limit < 1:
            return []
        payload = self._get_json(
            "/me/messages",
            params={
                "$top": str(min(limit, 100)),
                "$orderby": "receivedDateTime desc",
                "$select": "id,subject,sender,receivedDateTime,bodyPreview,body",
            },
            prefer_text=True,
        )
        value = payload.get("value", [])
        if not isinstance(value, list):
            raise TypeError("Microsoft Graph messages response has invalid value field")
        return [item for item in value if isinstance(item, dict)]

    def list_attachments(self, message_id: str) -> list[dict]:
        encoded_message_id = quote(message_id, safe="")
        payload = self._get_json(
            f"/me/messages/{encoded_message_id}/attachments",
            params={"$select": "id,name,contentType,size,isInline"},
        )
        value = payload.get("value", [])
        if not isinstance(value, list):
            raise TypeError("Microsoft Graph attachments response has invalid value field")

        attachments: list[dict] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            attachment_id = item.get("id")
            if not attachment_id:
                continue
            attachments.append(
                {
                    "id": str(attachment_id),
                    "name": str(item.get("name") or ""),
                    "size_bytes": int(item.get("size") or 0),
                    "content_type": item.get("contentType"),
                    "is_inline": bool(item.get("isInline")),
                }
            )
        return attachments

    def fetch_attachment(self, message_id: str, attachment_id: str) -> str:
        encoded_message_id = quote(message_id, safe="")
        encoded_attachment_id = quote(attachment_id, safe="")
        response = self._client.get(
            f"/me/messages/{encoded_message_id}/attachments/{encoded_attachment_id}/$value",
            headers=self._headers(),
        )
        self._raise_for_status(response)
        digest = hashlib.sha256(f"{message_id}:{attachment_id}".encode()).hexdigest()
        reference = f"graph-memory://{digest}"
        self._attachment_cache[reference] = response.content
        return reference

    def materialize(self, file_uri: str) -> bytes:
        try:
            return self._attachment_cache.pop(file_uri)
        except KeyError as exc:
            raise FileNotFoundError(f"Microsoft Graph attachment not cached: {file_uri}") from exc

    def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        prefer_text: bool = False,
    ) -> dict:
        response = self._client.get(
            path,
            params=params,
            headers=self._headers(prefer_text=prefer_text),
        )
        self._raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("Microsoft Graph returned a non-object JSON response")
        return payload

    def _headers(self, *, prefer_text: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }
        if prefer_text:
            headers["Prefer"] = 'outlook.body-content-type="text"'
        return headers

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        request_id = response.headers.get("request-id") or response.headers.get("client-request-id")
        suffix = f" request_id={request_id}" if request_id else ""
        raise RuntimeError(
            f"Microsoft Graph request failed with HTTP {response.status_code}.{suffix}"
        )
