from dataclasses import dataclass, field
from enum import Enum


class CommandKind(str, Enum):
    SEARCH_MATTER = "search_matter"
    ANALYZE_DOCUMENT = "analyze_document"
    LIST_DEADLINES = "list_deadlines"
    REVIEW_EMAIL = "review_email"
    CREATE_DRAFT = "create_draft"


@dataclass(frozen=True)
class CommandRequest:
    text: str
    source_device: str
    user_id: str
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandResult:
    command: CommandKind
    status: str
    message: str
    requires_approval: bool = False
