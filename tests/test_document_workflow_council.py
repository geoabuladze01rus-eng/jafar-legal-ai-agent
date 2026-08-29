from datetime import UTC, datetime

import pytest

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


class FakeProvider:
    def __init__(self, key: str, text: str) -> None:
        self.key = key
        self.text = text
        self.calls: list[ModelRequest] = []

    def available(self) -> bool:
        return True

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        return ModelResponse(self.key, "test-model", self.text, {})


def make_matter() -> Matter:
    now = datetime.now(UTC)
    return Matter(
        id="matter-1",
        title="Уголовное дело",
        matter_type=MatterType.CRIMINAL,
        client_name="Клиент",
        court_or_authority="Суд",
        case_number="123/2026",
        created_at=now,
        updated_at=now,
    )


def test_document_workflow_keeps_council_optional() -> None:
    store = MatterStore()
    store.create(make_matter())
    result = DocumentWorkflow(store, LegalAnalyzer()).process(
        "doc.txt",
        ExtractedDocument(
            filename="doc.txt",
            media_type="text/plain",
            text="По делу 123/2026 суд указал срок до 21.08.2026.",
        ),
    )
    assert result.council_review is None


def test_document_workflow_runs_council_after_deterministic_analysis() -> None:
    store = MatterStore()
    store.create(make_matter())
    openai = FakeProvider("openai", "primary review")
    qwen = FakeProvider("qwen", "independent review")
    policy = ProviderPrivacyPolicy(confidential_providers=("openai", "qwen"))
    service = CouncilReviewService(AICouncil({"openai": openai, "qwen": qwen}, privacy_policy=policy))
    workflow = DocumentWorkflow(store, LegalAnalyzer(), council_review_service=service)

    result = workflow.process(
        "doc.txt",
        ExtractedDocument(
            filename="doc.txt",
            media_type="text/plain",
            text="По делу 123/2026 суд указал срок до 21.08.2026.",
        ),
        run_council_review=True,
        allowed_providers=("openai", "qwen"),
    )

    assert result.analysis.key_facts
    assert result.council_review is not None
    assert result.council_review.council.providers == ("openai", "qwen")
    assert "EXTRACTED FACTS" in openai.calls[0].prompt
    assert "SOURCE DOCUMENT" in qwen.calls[0].prompt


def test_document_workflow_confidential_council_fails_closed_by_default() -> None:
    store = MatterStore()
    store.create(make_matter())
    providers = {
        "openai": FakeProvider("openai", "primary"),
        "qwen": FakeProvider("qwen", "review"),
    }
    workflow = DocumentWorkflow(
        store,
        LegalAnalyzer(),
        council_review_service=CouncilReviewService(AICouncil(providers)),
    )

    with pytest.raises(PermissionError):
        workflow.process(
            "doc.txt",
            ExtractedDocument(
                filename="doc.txt",
                media_type="text/plain",
                text="По делу 123/2026 суд указал срок до 21.08.2026.",
            ),
            run_council_review=True,
            allowed_providers=("openai", "qwen"),
        )
