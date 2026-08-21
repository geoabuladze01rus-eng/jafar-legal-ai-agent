from dataclasses import dataclass


@dataclass(frozen=True)
class OutlookSyncCursor:
    """Stable cursor for incremental mailbox synchronization."""

    received_after: str | None = None
    message_id: str | None = None


@dataclass(frozen=True)
class OutlookSyncPolicy:
    page_size: int = 20
    include_attachments: bool = True
    unread_only: bool = False
