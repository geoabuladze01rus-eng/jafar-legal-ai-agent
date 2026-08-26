from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .email_triage import EmailTriage
from .gmail_auth import (
    GmailCredentialManager,
    KeychainGmailCredentialStore,
)
from .lawyer_context import LawyerContext, LegalEmailAttachmentSnapshot


class GmailReadError(RuntimeError):
    """A safe Gmail list/read failure that contains no provider response body."""


@dataclass(frozen=True, slots=True)
class GmailAttachment:
    filename: str
    mime_type: str
    size_bytes: int
    stored_externally: bool


@dataclass(frozen=True, slots=True)
class GmailEmail:
    message_id: str
    thread_id: str
    sender: str
    subject: str
    received_at: datetime
    body_text: str
    snippet: str
    attachments: tuple[GmailAttachment, ...]
    external_links: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GmailLegalSelection:
    email: GmailEmail
    legal_relevance: float
    summary: str


class GmailReadOnlyClient(Protocol):
    """Deliberately exposes list/get only; no send, modify, trash or delete surface."""

    def list_message_ids(self, *, limit: int) -> list[str]: ...

    def get_message(self, message_id: str) -> dict[str, Any]: ...


class GoogleGmailReadOnlyClient:
    """Narrow adapter over Gmail API's two read operations used by Jafar."""

    # Live Gmail responses deliberately exclude every MIME body ``data`` field.
    # The bounded Gmail snippet is enough for the first local triage/summary slice;
    # attachment names, types and sizes remain visible as metadata.
    MESSAGE_METADATA_FIELDS = (
        "id,threadId,internalDate,snippet,"
        "payload(headers,mimeType,filename,body(attachmentId,size),"
        "parts(headers,mimeType,filename,body(attachmentId,size),"
        "parts(headers,mimeType,filename,body(attachmentId,size))))"
    )

    def __init__(self, service: Any) -> None:
        self._service = service

    def list_message_ids(self, *, limit: int) -> list[str]:
        if limit < 1:
            return []
        try:
            response = (
                self._service.users()
                .messages()
                .list(
                    userId="me",
                    labelIds=["INBOX"],
                    includeSpamTrash=False,
                    maxResults=min(limit, 100),
                )
                .execute()
            )
        except HttpError as exc:
            raise GmailReadError(self._safe_http_error("list", exc)) from None
        except Exception:  # noqa: BLE001 - never surface request or credential details.
            raise GmailReadError("Gmail API list operation failed.") from None
        messages = response.get("messages", []) if isinstance(response, dict) else []
        if not isinstance(messages, list):
            raise GmailReadError("Gmail вернул некорректный список писем.")
        return [str(item["id"]) for item in messages if isinstance(item, dict) and item.get("id")]

    def get_message(self, message_id: str) -> dict[str, Any]:
        if not message_id:
            raise ValueError("Gmail message id is required")
        try:
            response = (
                self._service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="full",
                    fields=self.MESSAGE_METADATA_FIELDS,
                )
                .execute()
            )
        except HttpError as exc:
            raise GmailReadError(self._safe_http_error("get", exc)) from None
        except Exception:  # noqa: BLE001 - never surface request or credential details.
            raise GmailReadError("Gmail API get operation failed.") from None
        if not isinstance(response, dict):
            raise GmailReadError("Gmail вернул некорректное письмо.")
        return response

    @staticmethod
    def _safe_http_error(operation: str, error: HttpError) -> str:
        status = getattr(getattr(error, "resp", None), "status", "unknown")
        return f"Gmail API read operation {operation} failed (HTTP {status})."


class GmailMessageParser:
    """Extract bounded message text and metadata without fetching attachment bytes."""

    MAX_BODY_CHARS = 40_000
    MAX_LINKS = 12

    def parse(self, raw: dict[str, Any]) -> GmailEmail:
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        headers = self._headers(payload.get("headers"))
        plain_parts: list[str] = []
        html_parts: list[str] = []
        attachments: list[GmailAttachment] = []
        self._walk_parts(payload, plain_parts, html_parts, attachments)

        body_text = "\n".join(item for item in plain_parts if item).strip()
        html_text = "\n".join(item for item in html_parts if item).strip()
        if not body_text and html_text:
            body_text = self._html_to_text(html_text)
        body_text = self._normalize_text(body_text)[: self.MAX_BODY_CHARS]
        snippet = self._normalize_text(str(raw.get("snippet") or ""))
        resolved_body_text = body_text or snippet
        link_source = f"{resolved_body_text}\n{html_text}"

        return GmailEmail(
            message_id=str(raw.get("id") or ""),
            thread_id=str(raw.get("threadId") or ""),
            sender=self._decode_header(headers.get("from", "")),
            subject=self._decode_header(headers.get("subject", "(без темы)")),
            received_at=self._received_at(raw, headers),
            body_text=resolved_body_text,
            snippet=snippet,
            attachments=tuple(attachments),
            external_links=self._extract_links(link_source),
        )

    def _walk_parts(
        self,
        part: dict[str, Any],
        plain_parts: list[str],
        html_parts: list[str],
        attachments: list[GmailAttachment],
    ) -> None:
        filename = self._decode_header(str(part.get("filename") or "")).strip()
        mime_type = str(part.get("mimeType") or "application/octet-stream").lower()
        body = part.get("body") if isinstance(part.get("body"), dict) else {}
        headers = self._headers(part.get("headers"))
        disposition = headers.get("content-disposition", "").lower()
        attachment_id = bool(body.get("attachmentId"))
        is_attachment = bool(filename) or "attachment" in disposition or (
            attachment_id and not mime_type.startswith("text/")
        )

        if is_attachment:
            attachments.append(
                GmailAttachment(
                    filename=filename or "вложение без имени",
                    mime_type=mime_type,
                    size_bytes=self._safe_size(body.get("size")),
                    stored_externally=attachment_id,
                )
            )
            return

        data = body.get("data")
        if isinstance(data, str) and mime_type in {"text/plain", "text/html"}:
            text = self._decode_body(data, headers.get("content-type", ""))
            if mime_type == "text/plain":
                plain_parts.append(text)
            else:
                html_parts.append(text)

        child_parts = part.get("parts")
        if isinstance(child_parts, list):
            for child in child_parts:
                if isinstance(child, dict):
                    self._walk_parts(child, plain_parts, html_parts, attachments)

    @classmethod
    def _decode_body(cls, encoded: str, content_type: str) -> str:
        try:
            padding = "=" * (-len(encoded) % 4)
            payload = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
        except (UnicodeEncodeError, ValueError, binascii.Error):
            return ""
        charset = "utf-8"
        if content_type:
            parsed = Message()
            parsed["content-type"] = content_type
            charset = parsed.get_content_charset() or charset
        try:
            return payload.decode(charset, errors="replace")
        except LookupError:
            return payload.decode("utf-8", errors="replace")

    @staticmethod
    def _headers(raw_headers: object) -> dict[str, str]:
        if not isinstance(raw_headers, list):
            return {}
        return {
            str(item.get("name") or "").lower(): str(item.get("value") or "")
            for item in raw_headers
            if isinstance(item, dict) and item.get("name")
        }

    @staticmethod
    def _decode_header(value: str) -> str:
        chunks: list[str] = []
        for item, charset in decode_header(value):
            if isinstance(item, bytes):
                try:
                    chunks.append(item.decode(charset or "utf-8", errors="replace"))
                except LookupError:
                    chunks.append(item.decode("utf-8", errors="replace"))
            else:
                chunks.append(item)
        return "".join(chunks).strip()

    @staticmethod
    def _received_at(raw: dict[str, Any], headers: dict[str, str]) -> datetime:
        internal_date = raw.get("internalDate")
        try:
            return datetime.fromtimestamp(int(str(internal_date)) / 1000, tz=UTC)
        except (TypeError, ValueError, OSError):
            try:
                value = parsedate_to_datetime(headers.get("date", ""))
                if value.tzinfo is None:
                    value = value.replace(tzinfo=UTC)
                return value.astimezone(UTC)
            except (TypeError, ValueError, OverflowError):
                pass
        return datetime.fromtimestamp(0, tz=UTC)

    @staticmethod
    def _safe_size(value: object) -> int:
        try:
            return max(int(str(value or 0)), 0)
        except ValueError:
            return 0

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value.replace("\x00", " ")).strip()

    @staticmethod
    def _html_to_text(value: str) -> str:
        parser = _VisibleTextHTMLParser()
        parser.feed(value)
        parser.close()
        return " ".join(parser.text).strip()

    def _extract_links(self, value: str) -> tuple[str, ...]:
        parser = _LinkHTMLParser()
        parser.feed(value)
        parser.close()
        candidates = parser.links + re.findall(r"https?://[^\s<>\"']+", value)
        result: list[str] = []
        for candidate in candidates:
            normalized = self._normalize_url(candidate)
            if normalized and normalized not in result:
                result.append(normalized)
                if len(result) == self.MAX_LINKS:
                    break
        return tuple(result)

    @staticmethod
    def _normalize_url(value: str) -> str | None:
        cleaned = value.rstrip(".,);]}>\u00bb")
        try:
            parsed = urlsplit(cleaned)
        except ValueError:
            return None
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path, "", ""))


class GmailReadOnlyGateway:
    """Fetch the newest relevant Gmail message and keep a safe current snapshot."""

    def __init__(
        self,
        client_factory: Callable[[], GmailReadOnlyClient],
        *,
        triage: EmailTriage | None = None,
        parser: GmailMessageParser | None = None,
        scan_limit: int = 20,
    ) -> None:
        self.client_factory = client_factory
        self.triage = triage or EmailTriage()
        self.parser = parser or GmailMessageParser()
        self.scan_limit = max(1, min(scan_limit, 100))

    def refresh_latest_legal_email(self, context: LawyerContext) -> GmailLegalSelection | None:
        client = self.client_factory()
        for message_id in client.list_message_ids(limit=self.scan_limit):
            raw_message = client.get_message(message_id)
            try:
                email = self.parser.parse(raw_message)
            except Exception:  # noqa: BLE001 - never surface mailbox content in parse errors.
                raise GmailReadError("Не удалось безопасно разобрать письмо Gmail.") from None
            decision = self.triage.classify(
                message_id=email.message_id,
                subject=email.subject,
                preview=email.body_text[:4000],
                attachment_count=len(email.attachments),
                attachment_names=tuple(item.filename for item in email.attachments),
            )
            if decision.action != "prepare_legal_analysis":
                continue
            selection = GmailLegalSelection(
                email=email,
                legal_relevance=decision.legal_relevance,
                summary=self._summary(email),
            )
            context.record_gmail_email(
                message_id=email.message_id,
                sender=email.sender,
                subject=email.subject,
                received_at=email.received_at.isoformat(),
                legal_relevance=decision.legal_relevance,
                summary=selection.summary,
                attachments=tuple(
                    LegalEmailAttachmentSnapshot(
                        filename=item.filename,
                        mime_type=item.mime_type,
                        size_bytes=item.size_bytes,
                    )
                    for item in email.attachments
                ),
                external_links=email.external_links,
            )
            return selection
        return None

    @staticmethod
    def _summary(email: GmailEmail) -> str:
        text = re.sub(r"\s+", " ", email.body_text).strip()
        text = re.sub(r"https?://[^\s<>\"']+", "[внешняя ссылка]", text)
        if not text:
            return "Текст письма отсутствует; доступны только тема и метаданные."
        if len(text) <= 420:
            return text
        boundary = max(text.rfind(". ", 0, 420), text.rfind("! ", 0, 420), text.rfind("? ", 0, 420))
        if boundary >= 160:
            return text[: boundary + 1]
        return text[:417].rstrip() + "…"


def make_local_gmail_gateway() -> GmailReadOnlyGateway:
    manager = GmailCredentialManager(KeychainGmailCredentialStore())

    def client_factory() -> GmailReadOnlyClient:
        credentials = manager.load_valid_credentials()
        try:
            service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        except Exception:  # noqa: BLE001 - never surface request or credential details.
            raise GmailReadError("Не удалось создать локальный Gmail read-only клиент.") from None
        return GoogleGmailReadOnlyClient(service)

    return GmailReadOnlyGateway(client_factory)


class _VisibleTextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth and data.strip():
            self.text.append(data.strip())


class _LinkHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)
