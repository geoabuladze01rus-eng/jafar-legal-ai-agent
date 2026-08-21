from dataclasses import dataclass


@dataclass(frozen=True)
class ReplyDraft:
    recipient: str
    subject: str
    body: str
    requires_approval: bool = True


def prepare_reply_draft(recipient: str, subject: str, body: str) -> ReplyDraft:
    """Draft-only policy: legal outbound communication always requires approval."""
    return ReplyDraft(
        recipient=recipient,
        subject=subject,
        body=body,
        requires_approval=True,
    )
