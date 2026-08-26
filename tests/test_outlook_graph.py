from __future__ import annotations

import json

import httpx

from jafar.outlook_graph import MicrosoftGraphOutlookClient
from jafar.outlook_provider import OutlookEmailProvider


def _response(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"] == "Bearer test-token"

    if request.url.path == "/v1.0/me/messages":
        assert request.headers["Prefer"] == 'outlook.body-content-type="text"'
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "msg-1",
                        "subject": "Юридические материалы",
                        "sender": {"emailAddress": {"address": "partner@example.com"}},
                        "receivedDateTime": "2026-08-25T18:00:00Z",
                        "bodyPreview": "Во вложении материалы.",
                        "body": {
                            "contentType": "text",
                            "content": "Просьба изучить поступившие материалы.",
                        },
                    }
                ]
            },
        )

    if request.url.path == "/v1.0/me/messages/msg-1/attachments":
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "doc-1",
                        "name": "note.txt",
                        "contentType": "text/plain",
                        "size": 128,
                        "isInline": False,
                    },
                    {
                        "id": "archive-1",
                        "name": "materials.zip",
                        "contentType": "application/zip",
                        "size": 4096,
                        "isInline": False,
                    },
                ]
            },
        )

    if request.url.path == "/v1.0/me/messages/msg-1/attachments/doc-1/$value":
        return httpx.Response(200, content=b"legal document text")

    raise AssertionError(f"Unexpected Graph request: {request.method} {request.url}")


def test_graph_client_maps_messages_and_keeps_attachment_bytes_in_memory_only():
    transport = httpx.MockTransport(_response)
    http_client = httpx.Client(transport=transport, base_url="https://graph.microsoft.com/v1.0")
    client = MicrosoftGraphOutlookClient("test-token", client=http_client)

    messages = client.list_messages(limit=1)
    attachments = client.list_attachments("msg-1")
    reference = client.fetch_attachment("msg-1", "doc-1")

    assert messages[0]["id"] == "msg-1"
    assert attachments[0]["size_bytes"] == 128
    assert reference.startswith("graph-memory://")
    assert client.materialize(reference) == b"legal document text"


def test_graph_client_and_outlook_provider_do_not_download_unsupported_zip():
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return _response(request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://graph.microsoft.com/v1.0")
    client = MicrosoftGraphOutlookClient("test-token", client=http_client)
    provider = OutlookEmailProvider(client, client)

    messages = provider.fetch_messages(limit=1)

    assert len(messages) == 1
    message = messages[0]
    assert message.body_text == "Просьба изучить поступившие материалы."
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "note.txt"
    assert len(message.provider_issues) == 1
    assert message.provider_issues[0].filename == "materials.zip"
    assert message.provider_issues[0].error_type == "UnsupportedAttachment"
    assert "/v1.0/me/messages/msg-1/attachments/archive-1/$value" not in requests


def test_graph_client_surfaces_http_failure_without_leaking_response_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            headers={"request-id": "request-123"},
            text=json.dumps({"error": {"message": "sensitive provider detail"}}),
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="https://graph.microsoft.com/v1.0")
    client = MicrosoftGraphOutlookClient("test-token", client=http_client)

    try:
        client.list_messages(limit=1)
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected Graph failure")

    assert "HTTP 401" in message
    assert "request-123" in message
    assert "sensitive provider detail" not in message
