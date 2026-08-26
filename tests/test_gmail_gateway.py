from __future__ import annotations

import base64
from typing import Any

from fastapi.testclient import TestClient

from jafar.command_runtime import JafarCommandRuntime
from jafar.gmail_auth import GmailSetupRequired
from jafar.gmail_gateway import (
    GmailMessageParser,
    GmailReadOnlyGateway,
    GoogleGmailReadOnlyClient,
)
from jafar.lawyer_context import LawyerContext
from jafar.main import app
from jafar.matters import MatterStore


def _encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _message(
    message_id: str,
    *,
    subject: str,
    body: str,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [
        {
            "mimeType": "text/plain",
            "filename": "",
            "headers": [{"name": "Content-Type", "value": "text/plain; charset=utf-8"}],
            "body": {"data": _encoded(body), "size": len(body.encode())},
        }
    ]
    parts.extend(attachments or [])
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "internalDate": "1787734800000",
        "snippet": body[:80],
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "Клиент <client@example.test>"},
                {"name": "Subject", "value": subject},
            ],
            "body": {"size": 0},
            "parts": parts,
        },
    }


class SyntheticReadOnlyGmailClient:
    def __init__(self) -> None:
        self.get_calls: list[str] = []
        self.messages = {
            "newest-news": _message(
                "newest-news",
                subject="Обновление офиса",
                body="Кофемашина будет обслуживаться в пятницу.",
            ),
            "latest-legal": _message(
                "latest-legal",
                subject="Кассационная жалоба — материалы для подготовки",
                body=(
                    "Прошу подготовить кассационную жалобу по судебному делу. "
                    "Срок подачи указан в постановлении. "
                    "Материалы также доступны по ссылке "
                    "https://files.example.test/case?signature=synthetic#section"
                ),
                attachments=[
                    {
                        "mimeType": "application/pdf",
                        "filename": "court-materials.pdf",
                        "headers": [
                            {"name": "Content-Disposition", "value": "attachment"}
                        ],
                        "body": {
                            "attachmentId": "remote-large-attachment",
                            "size": 50 * 1024 * 1024,
                        },
                    }
                ],
            ),
        }

    def list_message_ids(self, *, limit: int) -> list[str]:
        assert limit == 20
        return ["newest-news", "latest-legal"]

    def get_message(self, message_id: str) -> dict[str, Any]:
        self.get_calls.append(message_id)
        return self.messages[message_id]


class _SyntheticGoogleRequest:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def execute(self) -> dict[str, Any]:
        return self.response


class _SyntheticGoogleMessagesResource:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list(self, **kwargs) -> _SyntheticGoogleRequest:
        self.calls.append(("list", kwargs))
        return _SyntheticGoogleRequest({"messages": [{"id": "message-1"}]})

    def get(self, **kwargs) -> _SyntheticGoogleRequest:
        self.calls.append(("get", kwargs))
        return _SyntheticGoogleRequest({"id": "message-1"})


class _SyntheticGoogleService:
    def __init__(self) -> None:
        self.resource = _SyntheticGoogleMessagesResource()

    def users(self):
        return self

    def messages(self) -> _SyntheticGoogleMessagesResource:
        return self.resource


def test_google_client_uses_only_list_get_and_excludes_body_data_fields() -> None:
    service = _SyntheticGoogleService()
    client = GoogleGmailReadOnlyClient(service)

    assert client.list_message_ids(limit=20) == ["message-1"]
    assert client.get_message("message-1") == {"id": "message-1"}

    assert [name for name, _ in service.resource.calls] == ["list", "get"]
    list_args = service.resource.calls[0][1]
    get_args = service.resource.calls[1][1]
    assert list_args["labelIds"] == ["INBOX"]
    assert list_args["includeSpamTrash"] is False
    assert get_args["format"] == "full"
    assert "data" not in get_args["fields"]


def test_gateway_selects_latest_relevant_mail_without_fetching_attachment_bytes() -> None:
    client = SyntheticReadOnlyGmailClient()
    context = LawyerContext()
    gateway = GmailReadOnlyGateway(lambda: client)

    selection = gateway.refresh_latest_legal_email(context)

    assert selection is not None
    assert selection.email.message_id == "latest-legal"
    assert client.get_calls == ["newest-news", "latest-legal"]
    assert context.latest_legal_email is not None
    assert context.latest_legal_email.provider == "gmail"
    assert context.latest_legal_email.attachments[0].filename == "court-materials.pdf"
    assert context.latest_legal_email.attachments[0].size_bytes == 50 * 1024 * 1024
    assert context.latest_legal_email.external_links == ("https://files.example.test/case",)
    assert "signature=" not in selection.summary
    assert "[внешняя ссылка]" in selection.summary


def test_command_returns_summary_and_preserves_mail_as_followup_context() -> None:
    client = SyntheticReadOnlyGmailClient()
    context = LawyerContext()
    runtime = JafarCommandRuntime(
        MatterStore(),
        context,
        mail_gateway=GmailReadOnlyGateway(lambda: client),
    )

    latest = runtime.execute("latest_legal_email")
    followup = runtime.execute("attention_summary")

    assert "Кратко:" in latest.message
    assert latest.data["email"]["provider"] == "gmail"
    assert latest.data["email"]["attachments"][0]["downloaded"] is False
    assert latest.data["email"]["external_links"][0]["opened"] is False
    assert latest.data["email"]["mailbox_mutation_performed"] is False
    assert followup.data["latest_legal_email"]["message_id"] == "latest-legal"


def test_parser_never_decodes_inline_attachment_data_as_message_text() -> None:
    raw = _message(
        "legal-with-inline-bytes",
        subject="Судебное дело",
        body="Юридический текст письма.",
        attachments=[
            {
                "mimeType": "application/pdf",
                "filename": "evidence.pdf",
                "headers": [{"name": "Content-Disposition", "value": "attachment"}],
                "body": {"data": _encoded("SECRET ATTACHMENT BYTES"), "size": 23},
            }
        ],
    )

    parsed = GmailMessageParser().parse(raw)

    assert "SECRET ATTACHMENT BYTES" not in parsed.body_text
    assert parsed.attachments[0].filename == "evidence.pdf"


def test_metadata_only_message_detects_safe_link_from_bounded_snippet() -> None:
    parsed = GmailMessageParser().parse(
        {
            "id": "metadata-only",
            "snippet": "Материалы: https://files.example.test/case?signature=synthetic#part",
            "payload": {
                "headers": [{"name": "Subject", "value": "Судебные материалы"}],
                "mimeType": "multipart/mixed",
                "body": {"size": 0},
            },
        }
    )

    assert parsed.body_text.startswith("Материалы:")
    assert parsed.external_links == ("https://files.example.test/case",)


def test_runtime_returns_actionable_setup_gate_without_provider_details() -> None:
    class SetupRequiredGateway:
        def refresh_latest_legal_email(self, context: LawyerContext):
            raise GmailSetupRequired("synthetic provider detail that must remain hidden")

    runtime = JafarCommandRuntime(MatterStore(), mail_gateway=SetupRequiredGateway())

    result = runtime.execute("latest_legal_email")

    assert result.data["setup_required"] is True
    assert result.data["scope"] == "gmail.readonly"
    assert "synthetic provider detail" not in result.message


def test_http_command_e2e_uses_synthetic_gmail_only(monkeypatch) -> None:
    from jafar import main

    runtime = JafarCommandRuntime(
        MatterStore(),
        LawyerContext(),
        mail_gateway=GmailReadOnlyGateway(lambda: SyntheticReadOnlyGmailClient()),
    )
    monkeypatch.setattr(main, "command_runtime", runtime)
    monkeypatch.setattr(main.settings, "environment", "development")
    monkeypatch.setattr(main.settings, "api_key", None)

    with TestClient(app) as client:
        response = client.post(
            "/v1/command",
            json={
                "text": "Разбери последнее юридическое письмо",
                "user_id": "synthetic-e2e",
                "source_device": "mac",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "latest_legal_email"
    assert payload["data"]["email"]["message_id"] == "latest-legal"
    assert payload["data"]["email"]["mailbox_mutation_performed"] is False
