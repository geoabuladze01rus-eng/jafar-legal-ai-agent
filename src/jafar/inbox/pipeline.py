from dataclasses import dataclass

from jafar.inbox.classifier import MailClassification, classify_mail
from jafar.inbox.matter_matcher import MatterCandidate, match_matter


@dataclass(frozen=True)
class InboxPipelineResult:
    classification: MailClassification
    matter_candidates: tuple[MatterCandidate, ...]
    selected_matter_id: str | None
    requires_matter_confirmation: bool


def process_incoming_mail(
    *,
    message_id: str,
    subject: str,
    preview: str,
    sender: str,
    matters: list[dict[str, str]],
    has_attachments: bool = False,
) -> InboxPipelineResult:
    candidates = match_matter(subject, preview, sender, matters)
    selected = candidates[0].matter_id if candidates and candidates[0].score >= 0.90 else None
    needs_confirmation = len(candidates) > 1 or (candidates and candidates[0].score < 0.90)
    classification = classify_mail(
        message_id,
        subject,
        preview,
        has_attachments=has_attachments,
        matter_id=selected,
    )
    return InboxPipelineResult(
        classification=classification,
        matter_candidates=tuple(candidates),
        selected_matter_id=selected,
        requires_matter_confirmation=bool(needs_confirmation),
    )
