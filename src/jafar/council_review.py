from __future__ import annotations

from dataclasses import dataclass

from .ai_council import AICouncil, CouncilResult
from .legal_models import LegalAnalysis
from .model_router import ModelRequest


@dataclass(frozen=True, slots=True)
class CouncilReview:
    council: CouncilResult
    prompt: str


class CouncilReviewService:
    """Build an auditable AI Council request from deterministic legal-analysis output."""

    def __init__(self, council: AICouncil) -> None:
        self.council = council

    def review(
        self,
        *,
        document_text: str,
        analysis: LegalAnalysis,
        confidential: bool = True,
        allowed_providers: tuple[str, ...] | None = None,
        minimum_responses: int = 2,
    ) -> CouncilReview:
        prompt = self._build_prompt(document_text=document_text, analysis=analysis)
        result = self.council.run(
            ModelRequest(
                prompt=prompt,
                task="second_opinion",
                confidential=confidential,
                allowed_providers=allowed_providers,
            ),
            minimum_responses=minimum_responses,
        )
        return CouncilReview(council=result, prompt=prompt)

    @staticmethod
    def _build_prompt(*, document_text: str, analysis: LegalAnalysis) -> str:
        facts = "\n".join(f"- {item}" for item in analysis.key_facts) or "- none extracted"
        issues = "\n".join(
            f"- {item.title}: {item.description} [{item.risk.value}]" for item in analysis.issues
        ) or "- none extracted"
        deadlines = "\n".join(
            f"- {item.title}: {item.due_date or 'date unknown'}; confidence={item.confidence:.2f}"
            for item in analysis.deadlines
        ) or "- none extracted"
        missing = "\n".join(f"- {item}" for item in analysis.missing_information) or "- none"

        return (
            "You are an independent legal-review model inside Jafar AI Council.\n"
            "Treat the deterministic extraction below as the factual baseline, not as legal truth.\n"
            "Do not invent facts, citations, dates, court holdings, or evidence.\n"
            "Identify legal issues, weaknesses, contradictions, missing evidence, alternative interpretations, "
            "and questions requiring lawyer verification. Clearly distinguish document facts from your inferences.\n"
            "Return ONLY valid JSON with this shape: "
            '{"claims":[{"topic":"short stable topic","statement":"specific conclusion",'
            '"position":"support|oppose|uncertain","evidence_ids":["document"]}],'
            '"missing_evidence":["item"],"lawyer_questions":["question"]}. '
            "Use the same topic name for conclusions that address the same issue. "
            "If the source does not support a conclusion, use position=uncertain.\n\n"
            f"Task: {analysis.task.value}\n"
            f"Matter type: {analysis.matter_type.value}\n"
            f"Deterministic confidence: {analysis.confidence:.2f}\n\n"
            "EXTRACTED FACTS\n"
            f"{facts}\n\n"
            "DETECTED ISSUES\n"
            f"{issues}\n\n"
            "DETECTED DATES / DEADLINES REQUIRING VERIFICATION\n"
            f"{deadlines}\n\n"
            "MISSING INFORMATION\n"
            f"{missing}\n\n"
            "SOURCE DOCUMENT\n"
            f"{document_text}"
        )
