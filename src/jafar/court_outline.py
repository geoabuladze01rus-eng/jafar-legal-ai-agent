from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .attack_surface import AttackSurfaceReport
from .case_theory import CaseTheoryReport, TheoryStatus
from .hearing_preparation import HearingPreparationPlan
from .matter_intelligence_writer import MatterIntelligenceWriter, PersistenceOutcome


class OutlineKind(StrEnum):
    COURT_SPEECH = "court_speech"
    MOTION = "motion"


@dataclass(frozen=True, slots=True)
class LegalAuthorityRef:
    citation: str
    proposition: str
    verified: bool
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class OutlineSection:
    section_id: str
    topic: str
    thesis: str
    theory_status: TheoryStatus
    evidence_refs: tuple[dict[str, Any], ...]
    contradiction_points: tuple[str, ...]
    legal_questions: tuple[str, ...]
    authorities: tuple[LegalAuthorityRef, ...]
    hearing_questions: tuple[str, ...]
    requested_relief: tuple[str, ...]
    requires_lawyer_approval: bool = True


@dataclass(frozen=True, slots=True)
class CourtOutline:
    kind: OutlineKind
    title: str
    sections: tuple[OutlineSection, ...]
    unverified_authorities: tuple[str, ...]
    requires_source_verification: bool
    requires_lawyer_approval: bool = True


class CourtOutlineGenerator:
    """Build a source-traceable court-speech or motion outline.

    The generator does not invent statutes, case law or requested relief. Legal authorities
    and remedies must be supplied by the caller and remain subject to lawyer verification.
    """

    def build(
        self,
        *,
        theory: CaseTheoryReport,
        attack_surface: AttackSurfaceReport,
        hearing: HearingPreparationPlan,
        kind: OutlineKind = OutlineKind.COURT_SPEECH,
        title: str = "Рабочий каркас позиции",
        authorities_by_topic: dict[str, tuple[LegalAuthorityRef, ...]] | None = None,
        relief_by_topic: dict[str, tuple[str, ...]] | None = None,
    ) -> CourtOutline:
        authorities_by_topic = authorities_by_topic or {}
        relief_by_topic = relief_by_topic or {}
        attack_by_issue = {item.issue_id: item for item in attack_surface.items}
        hearing_by_issue = {step.issue_id: step for step in hearing.steps}

        sections: list[OutlineSection] = []
        unverified: list[str] = []
        for issue in theory.issues:
            attack = attack_by_issue.get(issue.issue_id)
            hearing_step = hearing_by_issue.get(issue.issue_id)
            authorities = authorities_by_topic.get(issue.topic, ())
            unverified.extend(item.citation for item in authorities if not item.verified)

            contradictions: list[str] = []
            if issue.status == TheoryStatus.CONTRADICTED:
                contradictions.append(
                    "По тезису имеется поддержанное источниками противоречие; необходимо изложить обе версии и их provenance."
                )
            if issue.status == TheoryStatus.REVIEW_REQUIRED:
                contradictions.append(
                    "Источник связан с нерешённым временным или иным review-сигналом; хронологию необходимо проверить до выступления."
                )
            if attack is not None:
                contradictions.extend(attack.reasons)

            legal_questions = self._legal_questions(issue.status, attack is not None)
            hearing_questions = ()
            if hearing_step is not None:
                hearing_questions = tuple(
                    dict.fromkeys((*hearing_step.primary_questions, *hearing_step.fallback_questions))
                )

            sections.append(
                OutlineSection(
                    section_id=f"outline:{issue.issue_id}",
                    topic=issue.topic,
                    thesis=issue.statement,
                    theory_status=issue.status,
                    evidence_refs=issue.source_refs,
                    contradiction_points=tuple(dict.fromkeys(contradictions)),
                    legal_questions=legal_questions,
                    authorities=authorities,
                    hearing_questions=hearing_questions,
                    requested_relief=relief_by_topic.get(issue.topic, ()),
                )
            )

        return CourtOutline(
            kind=kind,
            title=title,
            sections=tuple(sections),
            unverified_authorities=tuple(dict.fromkeys(unverified)),
            requires_source_verification=bool(unverified),
        )

    def snapshot(self, outline: CourtOutline) -> dict[str, Any]:
        return {
            "kind": outline.kind.value,
            "title": outline.title,
            "sections": [
                {
                    "section_id": section.section_id,
                    "topic": section.topic,
                    "thesis": section.thesis,
                    "theory_status": section.theory_status.value,
                    "evidence_refs": list(section.evidence_refs),
                    "contradiction_points": list(section.contradiction_points),
                    "legal_questions": list(section.legal_questions),
                    "authorities": [
                        {
                            "citation": authority.citation,
                            "proposition": authority.proposition,
                            "verified": authority.verified,
                            "source_url": authority.source_url,
                        }
                        for authority in section.authorities
                    ],
                    "hearing_questions": list(section.hearing_questions),
                    "requested_relief": list(section.requested_relief),
                    "requires_lawyer_approval": section.requires_lawyer_approval,
                }
                for section in outline.sections
            ],
            "unverified_authorities": list(outline.unverified_authorities),
            "requires_source_verification": outline.requires_source_verification,
            "requires_lawyer_approval": outline.requires_lawyer_approval,
        }

    def persist(self, outline: CourtOutline, *, writer: MatterIntelligenceWriter, owner_id: str, matter_id: str, analysis_run_id: str) -> PersistenceOutcome:
        data = self.snapshot(outline)
        return writer.write(owner_id=owner_id, matter_id=matter_id, kind="hearing", payload={"goal": outline.title, "theses": [section.thesis for section in outline.sections], "questions": [question for section in outline.sections for question in section.hearing_questions], "documents": [str(ref.get("evidence_id", "")) for section in outline.sections for ref in section.evidence_refs], "available": True, "outline": data, "kind": data["kind"]}, analysis_run_id=analysis_run_id)

    @staticmethod
    def _legal_questions(status: TheoryStatus, attacked: bool) -> tuple[str, ...]:
        questions = [
            "Какое юридически значимое обстоятельство подтверждает или опровергает этот тезис?",
            "Какие требования закона к относимости, допустимости, достоверности и достаточности доказательств применимы после проверки актуальных норм?",
        ]
        if status == TheoryStatus.UNSUPPORTED:
            questions.append("Может ли тезис использоваться без установленного первичного источника и его процессуальной проверки?")
        if status in {TheoryStatus.CONTRADICTED, TheoryStatus.REVIEW_REQUIRED}:
            questions.append("Как выявленное противоречие влияет на оценку доказательства после проверки применимого права и судебной практики?")
        if attacked:
            questions.append("Требуется ли процессуальное ходатайство или иной способ проверки; конкретный инструмент определяет адвокат.")
        return tuple(questions)
