from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VisualTemplate(StrEnum):
    RESONANT_CASE = "resonant_case"
    INVESTIGATOR_THINKS = "investigator_thinks"
    WHAT_TO_DO = "what_to_do"
    INVESTIGATION_ERROR = "investigation_error"
    COURT_PRACTICE = "court_practice"


class VisualCategory(StrEnum):
    DOCUMENTARY_PHOTO_BRANDED = "DOCUMENTARY_PHOTO_BRANDED"
    EDITORIAL_CINEMATIC = "EDITORIAL_CINEMATIC"
    LEGAL_INFOGRAPHIC = "LEGAL_INFOGRAPHIC"
    DOCUMENT_RECONSTRUCTION = "DOCUMENT_RECONSTRUCTION"
    COURT_PRACTICE = "COURT_PRACTICE"
    BREAKING = "BREAKING"


@dataclass(frozen=True, slots=True)
class VisualDecision:
    template: VisualTemplate
    category: VisualCategory
    accent: str
    requires_provenance: bool
    ai_allowed: bool
    prompt_prefix: str
    rationale: str


MASTER_TEMPLATES: dict[VisualTemplate, dict[str, str]] = {
    VisualTemplate.RESONANT_CASE: {
        "accent": "crime_red",
        "prompt": (
            "Master template RESONANT_CASE. Dark legal documentary. "
            "One dominant subject, strong negative space in the lower third, "
            "graphite/deep-navy palette, cold directional light, restrained red accent. "
            "No fake police insignia, no sensational tabloid elements. "
        ),
    },
    VisualTemplate.INVESTIGATOR_THINKS: {
        "accent": "muted_gold",
        "prompt": (
            "Master template INVESTIGATOR_THINKS. Investigative office atmosphere: "
            "desk, closed case file, practical lamp, corridor or closed door, "
            "cold cinematic lighting, restrained muted-gold accent, premium editorial realism. "
        ),
    },
    VisualTemplate.WHAT_TO_DO: {
        "accent": "crime_red",
        "prompt": (
            "Master template WHAT_TO_DO. Practical procedural instruction visual: "
            "doorway, corridor, file folder or neutral law-enforcement environment, "
            "clear hierarchy, large safe negative space for a short headline, restrained red accent. "
        ),
    },
    VisualTemplate.INVESTIGATION_ERROR: {
        "accent": "crime_red",
        "prompt": (
            "Master template INVESTIGATION_ERROR. Anonymous document/protocol reconstruction, "
            "one visually emphasized fragment without readable personal data, graphite background, "
            "cold light, restrained red frame, serious forensic editorial style. "
        ),
    },
    VisualTemplate.COURT_PRACTICE: {
        "accent": "muted_gold",
        "prompt": (
            "Master template COURT_PRACTICE. Court building, courtroom corridor or neutral judicial file, "
            "graphite/deep-navy palette, restrained muted-gold accent, formal premium editorial style. "
        ),
    },
}


def select_visual_decision(
    *,
    topic: str,
    title: str,
    is_news: bool,
    public_resonance: str,
    documentary_photo_verified: bool,
) -> VisualDecision:
    haystack = f"{topic} {title}".lower()

    if is_news and public_resonance in {"high", "breaking"}:
        if documentary_photo_verified:
            return VisualDecision(
                template=VisualTemplate.RESONANT_CASE,
                category=VisualCategory.DOCUMENTARY_PHOTO_BRANDED,
                accent="crime_red",
                requires_provenance=True,
                ai_allowed=False,
                prompt_prefix="",
                rationale="High-resonance real event: verified documentary photo has priority.",
            )
        return VisualDecision(
            template=VisualTemplate.RESONANT_CASE,
            category=VisualCategory.BREAKING,
            accent="crime_red",
            requires_provenance=False,
            ai_allowed=True,
            prompt_prefix=MASTER_TEMPLATES[VisualTemplate.RESONANT_CASE]["prompt"]
            + "This is an explicitly editorial illustration, not a reconstruction of the real event. ",
            rationale="No verified documentary photo: use an honest branded editorial visual.",
        )

    if any(token in haystack for token in ("верховн", "конституционн", "судебн", "суд ", "практик")):
        template = VisualTemplate.COURT_PRACTICE
        category = VisualCategory.COURT_PRACTICE
    elif any(token in haystack for token in ("что делать", "обыск", "допрос", "задержан", "повестк")):
        template = VisualTemplate.WHAT_TO_DO
        category = VisualCategory.EDITORIAL_CINEMATIC
    elif any(token in haystack for token in ("ошибк", "нарушен", "протокол", "недопустим")):
        template = VisualTemplate.INVESTIGATION_ERROR
        category = VisualCategory.DOCUMENT_RECONSTRUCTION
    elif any(token in haystack for token in ("следователь", "следствие думает", "логика следств")):
        template = VisualTemplate.INVESTIGATOR_THINKS
        category = VisualCategory.EDITORIAL_CINEMATIC
    else:
        template = VisualTemplate.RESONANT_CASE
        category = VisualCategory.EDITORIAL_CINEMATIC

    cfg = MASTER_TEMPLATES[template]
    return VisualDecision(
        template=template,
        category=category,
        accent=cfg["accent"],
        requires_provenance=False,
        ai_allowed=True,
        prompt_prefix=cfg["prompt"],
        rationale="Selected by editorial topic/template rules.",
    )


def visual_preflight_score(
    *,
    decision: VisualDecision,
    image_present: bool,
    image_size_bytes: int,
    prompt: str,
    source_url: str | None,
    provenance_verified: bool,
    ai_generated: bool,
) -> tuple[int, str]:
    if not image_present or image_size_bytes <= 0:
        return 0, "manual_review"

    score = 82
    if image_size_bytes >= 10000:
        score += 4
    elif image_size_bytes < 1000:
        score -= 20

    if len(prompt.strip()) >= 40 or not ai_generated:
        score += 3

    if decision.category is VisualCategory.DOCUMENTARY_PHOTO_BRANDED:
        if not source_url or not provenance_verified or ai_generated:
            return 0, "manual_review"
        score += 8

    if decision.category is VisualCategory.BREAKING and ai_generated:
        score -= 2

    score = max(0, min(score, 100))
    if score >= 80:
        return score, "approved"
    if score >= 70:
        return score, "regenerate"
    return score, "manual_review"
