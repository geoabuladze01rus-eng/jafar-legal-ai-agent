from jafar.ai_council import CouncilResult
from jafar.council_evidence import CouncilEvidenceService
from jafar.council_review import CouncilReview
from jafar.model_router import ModelResponse


def response(provider: str, text: str) -> ModelResponse:
    return ModelResponse(provider=provider, model="test", text=text, metadata={})


def test_evidence_service_detects_structured_model_contradiction() -> None:
    review = CouncilReview(
        council=CouncilResult(
            responses=(
                response(
                    "openai",
                    '{"claims":[{"topic":"appeal_deadline","statement":"deadline preserved",'
                    '"position":"support","evidence_ids":["document"]}],'
                    '"missing_evidence":[],"lawyer_questions":[]}',
                ),
                response(
                    "qwen",
                    '{"claims":[{"topic":"appeal_deadline","statement":"deadline expired",'
                    '"position":"oppose","evidence_ids":["document"]}],'
                    '"missing_evidence":[],"lawyer_questions":[]}',
                ),
            ),
            failed_providers=(),
            disagreements=("different",),
        ),
        prompt="p",
    )

    report = CouncilEvidenceService().build(review)

    assert len(report.claims) == 2
    assert report.contradictions
    assert report.requires_human_review is True


def test_evidence_service_preserves_gaps_and_lawyer_questions() -> None:
    review = CouncilReview(
        council=CouncilResult(
            responses=(
                response(
                    "kimi",
                    '{"claims":[],"missing_evidence":["proof of service"],'
                    '"lawyer_questions":["When was the order served?"]}',
                ),
            ),
            failed_providers=(),
            disagreements=(),
        ),
        prompt="p",
    )

    report = CouncilEvidenceService().build(review)

    assert report.evidence_gaps == ("proof of service",)
    assert report.lawyer_questions == ("When was the order served?",)
    assert report.requires_human_review is True


def test_evidence_service_flags_malformed_provider_without_inventing_claims() -> None:
    review = CouncilReview(
        council=CouncilResult(
            responses=(response("deepseek", "not-json"),),
            failed_providers=(),
            disagreements=(),
        ),
        prompt="p",
    )

    report = CouncilEvidenceService().build(review)

    assert report.claims == ()
    assert report.malformed_providers == ("deepseek",)
    assert report.requires_human_review is True
