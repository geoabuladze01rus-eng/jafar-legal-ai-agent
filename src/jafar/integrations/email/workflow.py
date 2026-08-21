from dataclasses import dataclass

from jafar.integrations.email.models import EmailTriageResult, LegalEmail
from jafar.integrations.email.triage import triage_email


@dataclass(frozen=True)
class EmailProcessingResult:
    email: LegalEmail
    triage: EmailTriageResult
    attachment_ids: list[str]


def process_email(email: LegalEmail) -> EmailProcessingResult:
    """Classify first; downloading/analysis is an explicit later stage."""
    result = triage_email(email)
    attachment_ids = [item.attachment_id for item in email.attachments]
    return EmailProcessingResult(email=email, triage=result, attachment_ids=attachment_ids)
