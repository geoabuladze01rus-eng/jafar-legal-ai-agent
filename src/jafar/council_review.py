from __future__ import annotations

from dataclasses import dataclass

from .ai_council import AICouncil, CouncilResult
from .legal_models import LegalAnalysis
from .model_router import ModelRequest


@dataclass(frozen=True, slots=True)
class CouncilEvidenceInput:
    evidence_id: str
    text: str
    page: int | None = None
    chunk_index: int | None = None


@dataclass(frozen=True, slots=True)
class CouncilReview:
    council: CouncilResult
    prompt: str
    allowed_evidence_ids: tuple[str, ...]


class CouncilReviewService:
    """Build an auditable AI Council request from deterministic legal-analysis output."""

    def __init__(self, council: AICouncil) -> None:
        self.council = council

    def review(
        self,
        *,
        document_text: str,
        analysis: LegalAnalysis,
        document_name: str = "document",
        document_fingerprint: str | None = None,
        evidence_inputs: tuple[CouncilEvidenceInput, ...] | None = None,
        confidential: bool = True,
        allowed_providers: tuple[str, ...] | None = None,
        minimum_responses: int = 2,
    ) -> CouncilReview:
        if evidence_inputs:
            allowed_evidence_ids = tuple(item.evidence_id for item in evidence_inputs)
        else:
            fingerprint = document_fingerprint or "unidentified"
            allowed_evidence_ids = (f"document:{fingerprint}",)
        prompt = self._build_prompt(
            document_text=document_text,
            analysis=analysis,
            document_name=document_name,
            allowed_evidence_ids=allowed_evidence_ids,
            evidence_inputs=evidence_inputs or (),
        )
        result = self.council.run(
            ModelRequest(
                prompt=prompt,
                task="second_opinion",
                confidential=confidential,
                allowed_providers=allowed_providers,
            ),
            minimum_responses=minimum_responses,
        )
        return CouncilReview(
            council=result,
            prompt=prompt,
            allowed_evidence_ids=allowed_evidence_ids,
        )

    @staticmethod
    def _build_prompt(
        *,
        document_text: str,
        analysis: LegalAnalysis,
        document_name: str,
        allowed_evidence_ids: tuple[str, ...],
        evidence_inputs: tuple[CouncilEvidenceInput, ...],
    ) -> str:
        facts = "\n".join(f"- {item}" for item in analysis.key_facts) or "- none extracted"
        issues = "\n".join(
            f"- {item.title}: {item.description} [{item.risk.value}]" for item in analysis.issues
        ) or "- none extracted"
        deadlines = "\n".join(
            f"- {item.title}: {item.due_date or 'date unknown'}; confidence={item.confidence:.2f}"
            for item in analysis.deadlines
        ) or "- none extracted"
        missing = "\n".join(f"- {item}" for item in analysis.missing_information) or "- none"
        evidence_ids = "\n".join(f"- {item}" for item in allowed_evidence_ids)
        evidence_context = "\n\n".join(
            (
                f"EVIDENCE ID: {item.evidence_id}\n"
                f"PAGE: {item.page if item.page is not None else 'n/a'}\n"
                f"CHUNK: {item.chunk_index if item.chunk_index is not None else 'n/a'}\n"
                f"TEXT:\n{item.text}"
            )
            for item in evidence_inputs
        )

        return (
            "You are an independent legal-review model inside Jafar AI Council.\n"
            "Treat the deterministic extraction below as the factual baseline, not as legal truth.\n"
            "Do not invent facts, citations, dates, court holdings, evidence, or evidence identifiers.\n"
            "Return ONLY valid JSON with keys: claims, missing_evidence, lawyer_questions.\n"
            "Each claim must contain: topic, statement, position, evidence_ids.\n"
            "For evidence_ids, use ONLY identifiers listed under ALLOWED EVIDENCE IDS. "
            "Cite the most specific page/chunk source that directly supports the claim. "
            "If a claim is not supported by a listed source, use an empty evidence_ids list.\n"
            "Identify legal issues, weaknesses, contradictions, missing evidence, alternative interpretations, "
            "and questions requiring lawyer verification. Clearly distinguish document facts from your inferences.\n\n"
            f"Task: {analysis.task.value}\n"
            f"Matter type: {analysis.matter_type.value}\n"
            f"Deterministic confidence: {analysis.confidence:.2f}\n\n"
            "ALLOWED EVIDENCE IDS\n"
            f"{evidence_ids}\n\n"
            "EXTRACTED FACTS\n"
            f"{facts}\n\n"
            "DETECTED ISSUES\n"
            f"{issues}\n\n"
            "DETECTED DATES / DEADLINES REQUIRING VERIFICATION\n"
            f"{deadlines}\n\n"
            "MISSING INFORMATION\n"
            f"{missing}\n\n"
            "EVIDENCE FRAGMENTS\n"
            f"{evidence_context or 'No fragment-level provenance supplied.'}\n\n"
            "SOURCE DOCUMENT\n"
            f"Name: {document_name}\n"
            f"{document_text}"
        )
