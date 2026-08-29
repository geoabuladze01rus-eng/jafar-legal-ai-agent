from datetime import UTC, datetime

from jafar.ai_council import AICouncil
from jafar.council_review import CouncilReviewService
from jafar.document_intake import ExtractedDocument
from jafar.document_workflow import DocumentWorkflow
from jafar.domains import MatterType
from jafar.legal_analysis import LegalAnalyzer
from jafar.legal_models import Matter
from jafar.matters import MatterStore
from jafar.model_router import ModelRequest, ModelResponse
from jafar.privacy_policy import ProviderPrivacyPolicy


class CapturingProvider:
    key = "openai"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def available(self) -> bool:
        return True

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(self.key, "test", '{"claims": [], "missing_evidence": [], "lawyer_questions": []}', {})


def test_workflow_passes_page_chunk_ids_to_council_prompt() -> None:
    store = MatterStore()
    now = datetime.now(UTC)
    store.create(
        Matter(
            id="m1",
            title="Case",
            matter_type=MatterType.CRIMINAL,
            case_number="123/2026",
            created_at=now,
            updated_at=now,
        )
    )
    provider = CapturingProvider()
    policy = ProviderPrivacyPolicy(confidential_providers=("openai",))
    council = AICouncil({"openai": provider}, privacy_policy=policy)
    workflow = DocumentWorkflow(
        store,
        LegalAnalyzer(),
        council_review_service=CouncilReviewService(council),
    )
    document = ExtractedDocument(
        filename="case.pdf",
        media_type="application/pdf",
        text="По делу 123/2026 первая страница.\nНа второй странице суд указал срок.",
        pages=(
            "По делу 123/2026 первая страница.",
            "На второй странице суд указал срок.",
        ),
    )

    result = workflow.process(
        "case.pdf",
        document,
        run_council_review=True,
        allowed_providers=("openai",),
        council_minimum_responses=1,
    )

    assert result.council_review is not None
    assert len(result.council_review.allowed_evidence_ids) == 2
    assert any(":page:1:chunk:0" in item for item in result.council_review.allowed_evidence_ids)
    assert any(":page:2:chunk:1" in item for item in result.council_review.allowed_evidence_ids)
    prompt = provider.requests[0].prompt
    assert "EVIDENCE FRAGMENTS" in prompt
    assert "PAGE: 2" in prompt
    assert ":page:2:chunk:1" in prompt
