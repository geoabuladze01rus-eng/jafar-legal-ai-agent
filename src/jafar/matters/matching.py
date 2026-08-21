from dataclasses import dataclass
import re


@dataclass(frozen=True)
class MatterRef:
    matter_id: str
    title: str
    client: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatterMatch:
    matter_id: str | None
    confidence: float
    reason: str
    create_candidate: bool = False


def match_matter(text: str, matters: list[MatterRef]) -> MatterMatch:
    normalized = text.casefold()
    best: MatterMatch | None = None

    for matter in matters:
        terms = (matter.title, matter.client or "", *matter.aliases)
        hits = sum(1 for term in terms if term and term.casefold() in normalized)
        if hits == 0:
            continue
        confidence = min(0.95, 0.55 + 0.15 * hits)
        candidate = MatterMatch(matter.matter_id, confidence, f"Совпали признаки дела: {hits}")
        if best is None or candidate.confidence > best.confidence:
            best = candidate

    if best:
        return best

    # New-matter detection is deliberately only a candidate; creation requires approval.
    if re.search(r"новое дело|новый клиент|обращение|договор на сопровождение", normalized):
        return MatterMatch(None, 0.70, "Обнаружены признаки нового дела.", create_candidate=True)

    return MatterMatch(None, 0.0, "Недостаточно признаков для привязки к делу.")
