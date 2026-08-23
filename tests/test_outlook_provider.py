from __future__ import annotations

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


def test_provider_fetches_only_supported_non_inline_attachments():
    client = FakeOutlook()
    messages = OutlookEmailProvider(client).fetch_messages(limit=1)
    assert len(messages) == 1
    assert messages[0].sender == "client@example.com"
    assert messages[0].attachments[0].filename == "court.pdf"
    assert client.fetched == ["pdf-1"]


def test_provider_skips_oversized_attachment():
    class LargeAttachmentClient(FakeOutlook):
        def list_attachments(self, message_id):
            return [{"id":"large","name":"large.pdf","size_bytes":101,"content_type":"application/pdf","is_inline":False}]

    client = LargeAttachmentClient()
    messages = OutlookEmailProvider(client, OutlookProviderConfig(max_attachment_bytes=100)).fetch_messages()
    assert messages[0].attachments == ()
    assert client.fetched == []
