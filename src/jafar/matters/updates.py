from dataclasses import dataclass
from datetime import datetime, timezone

from jafar.matters.models import Matter


@dataclass(frozen=True)
class MatterUpdateProposal:
    matter_id: str
    source_id: str
    summary: str
    suggested_aliases: tuple[str, ...] = ()
    suggested_status: str | None = None
    requires_approval: bool = True


def propose_update(matter: Matter, source_id: str, summary: str, *, aliases: tuple[str, ...] = (), status: str | None = None) -> MatterUpdateProposal:
    return MatterUpdateProposal(
        matter_id=matter.matter_id,
        source_id=source_id,
        summary=summary,
        suggested_aliases=aliases,
        suggested_status=status,
        requires_approval=True,
    )


def apply_approved_update(matter: Matter, proposal: MatterUpdateProposal) -> Matter:
    aliases = tuple(dict.fromkeys((*matter.aliases, *proposal.suggested_aliases)))
    return Matter(
        matter_id=matter.matter_id,
        title=matter.title,
        matter_type=matter.matter_type,
        status=proposal.suggested_status or matter.status,
        client_id=matter.client_id,
        case_number=matter.case_number,
        aliases=aliases,
        created_at=matter.created_at,
        updated_at=datetime.now(timezone.utc),
    )
