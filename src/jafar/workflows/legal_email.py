from dataclasses import dataclass

from jafar.integrations.email.models import LegalEmail
from jafar.integrations.email.triage import triage_email


@dataclass(frozen=True)
class LegalEmailWorkflowResult:
    message_id: str
    relevant: bool
    confidence: float
    reasons: list[str]
    attachment_ids: list[str]
    next_action: str


def process_legal_email(email: LegalEmail) -> LegalEmailWorkflowResult:
    triage = triage_email(email)
    if not triage.is_legal_relevant:
        next_action = "archive_triage_result"
    elif email.attachments:
        next_action = "ingest_attachments_and_match_matter"
    else:
        next_action = "analyze_email_and_match_matter"

    return LegalEmailWorkflowResult(
        message_id=email.message_id,
        relevant=triage.is_legal_relevant,
        confidence=triage.confidence,
        reasons=triage.reasons,
        attachment_ids=[a.attachment_id for a in email.attachments],
        next_action=next_action,
    )
