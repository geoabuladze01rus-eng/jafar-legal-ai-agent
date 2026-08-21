from dataclasses import dataclass
import re

from jafar.integrations.email.models import LegalEmail
from jafar.storage.documents import StoredDocument


@dataclass(frozen=True)
class MatterCandidate:
    matter_id: str
    score: float
    reasons: list[str]


def match_email_to_matters(email: LegalEmail, matters: list[StoredDocument]) -> list[MatterCandidate]:
    """Conservative lexical matching; ambiguous matches must be reviewed."""
    haystack = f"{email.subject}\n{email.body_preview}".lower()
    candidates: list[MatterCandidate] = []
    for matter in matters:
        if not matter.matter_id:
            continue
        tokens = re.findall(r"[\w№-]+", matter.filename.lower())
        hits = [token for token in tokens if len(token) >= 4 and token in haystack]
        if hits:
            score = min(1.0, len(set(hits)) / 3)
            candidates.append(MatterCandidate(matter.matter_id, score, [f"Совпадения: {', '.join(sorted(set(hits)))}"]))
    return sorted(candidates, key=lambda item: (-item.score, item.matter_id))
