from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MailMessage:
    message_id: str
    sender: str
    subject: str
    body: str
    attachment_ids: list[str]


@dataclass(frozen=True)
class DriveFile:
    file_id: str
    name: str
    mime_type: str
    download_reference: str | None = None


class MailProvider(Protocol):
    def list_messages(self, *, since_cursor: str | None = None) -> list[MailMessage]: ...


class DriveProvider(Protocol):
    def list_files(self, *, since_cursor: str | None = None) -> list[DriveFile]: ...


class LegalInboxOrchestrator:
    """Provider-neutral boundary for Gmail/Drive ingestion.

    Credentials and provider-specific OAuth are deliberately kept outside the
    legal core. Messages/files are passed into the existing document analysis
    and indexing pipelines only after provider authentication succeeds.
    """

    def __init__(self, mail: MailProvider, drive: DriveProvider) -> None:
        self.mail = mail
        self.drive = drive

    def collect(self, *, mail_cursor: str | None = None, drive_cursor: str | None = None):
        return {
            "messages": self.mail.list_messages(since_cursor=mail_cursor),
            "files": self.drive.list_files(since_cursor=drive_cursor),
        }
