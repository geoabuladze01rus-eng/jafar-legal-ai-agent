from dataclasses import dataclass
from enum import Enum


class ApprovalAction(str, Enum):
    SEND_EMAIL = "send_email"
    FILE_DOCUMENT = "file_document"
    CONTACT_THIRD_PARTY = "contact_third_party"


@dataclass(frozen=True)
class ApprovalRequest:
    action: ApprovalAction
    description: str
    approved: bool = False


def require_approval(action: ApprovalAction, description: str) -> ApprovalRequest:
    return ApprovalRequest(action=action, description=description, approved=False)
