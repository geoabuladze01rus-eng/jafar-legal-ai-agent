from __future__ import annotations

import pytest

from jafar.attachment_materializer import InMemoryAttachmentMaterializer
from jafar.outlook_provider import OutlookEmailProvider, OutlookProviderConfig


class FakeOutlook:
    def __init__(self):
        self.fetched = []

    def list_messages(self, *, limit=25):
        return [{"id":"msg-1","sender":{"emailAddress":{"address":"client@example.com"}},"subject":"Документы","receivedDateTime":"2026-08-23T07:00:00Z","bodyPreview":"Во вложении материалы."}]

    def list_attachments(self, message_id):
        return [
            {"id":"pdf-1","name":"court.pdf","size_bytes":1000,"content_type":"application/pdf","is_inline":False},
            {"id":"zip-1","name":"archive.zip","size_bytes":1000,"content_type":"application/zip","is_inline":False},
            {"id":"inline-1","name":"logo.pdf","size_bytes":1000,"content_type":"application/pdf","is_inline":True},
        ]

    def fetch_attachment(self, message_id, attachment_id):
        self.fetched.append(attachment_id)
        return f"file://{attachment_id}"


def test_provider_materializes_supported_attachment_bytes():
    client = FakeOutlook()
    materializer = InMemoryAttachmentMaterializer({"file://pdf-1": b"real-pdf-bytes"})
    messages = OutlookEmailProvider(client, materializer).fetch_messages(limit=1)
    assert len(messages) == 1
    assert messages[0].sender == "client@example.com"
    assert messages[0].attachments[0].filename == "court.pdf"
    assert messages[0].attachments[0].content == b"real-pdf-bytes"
    assert client.fetched == ["pdf-1"]


def test_provider_skips_oversized_attachment():
    class LargeAttachmentClient(FakeOutlook):
        def list_attachments(self, message_id):
            return [{"id":"large","name":"large.pdf","size_bytes":101,"content_type":"application/pdf","is_inline":False}]

    client = LargeAttachmentClient()
    materializer = InMemoryAttachmentMaterializer({})
    messages = OutlookEmailProvider(client, materializer, OutlookProviderConfig(max_attachment_bytes=100)).fetch_messages()
    assert messages[0].attachments == ()
    assert client.fetched == []


def test_provider_surfaces_materialization_failure():
    client = FakeOutlook()
    materializer = InMemoryAttachmentMaterializer({})
    with pytest.raises(FileNotFoundError):
        OutlookEmailProvider(client, materializer).fetch_messages(limit=1)
