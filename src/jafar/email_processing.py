from __future__ import annotations

from dataclasses import dataclass

from .email_reply_draft import EmailReplyDraft, EmailReplyDraftGenerator
from .email_triage import EmailTriage, EmailTriageDecision
from .inbox import InboxMessage


@dataclass(frozen=True, slots=True)
class EmailProcessingResult:
    triage: EmailTriageDecision
    reply_draft: EmailReplyDraft | None = None


class EmailProcessor:
    """Coordinates triage and optional review-only reply drafting."""

    def __init__(
        self,
        triage: EmailTriage | None = None,
        draft_generator: EmailReplyDraftGenerator | None = None,
    ) -> None:
        self.triage = triage or EmailTriage()
        self.draft_generator = draft_generator or EmailReplyDraftGenerator()

    def process(self, message: InboxMessage) -> EmailProcessingResult:
        decision = self.triage.classify(
            message_id=message.message_id,
            subject=message.subject,
            preview=message.body_text[:4000],
            attachment_count=len(message.attachments),
        )
        draft = None
        if decision.action == "prepare_legal_analysis":
            draft = self.draft_generator.create(message)
        return EmailProcessingResult(triage=decision, reply_draft=draft)
