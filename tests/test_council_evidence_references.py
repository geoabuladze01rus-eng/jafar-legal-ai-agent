from jafar.ai_council import CouncilResult
from jafar.council_evidence import CouncilEvidenceService
from jafar.council_review import CouncilReview
from jafar.model_router import ModelResponse


def test_invented_evidence_id_is_rejected_and_requires_review() -> None:
    response = ModelResponse(
        provider="qwen",
        model="test",
        text='{"claims":[{"topic":"date","statement":"Дата 13 августа","position":"supports","evidence_ids":["invented:42"]}],"missing_evidence":[],"lawyer_questions":[]}',
        metadata={},
    )
    review = CouncilReview(
        council=CouncilResult(
            responses=(response,),
            failed_providers=(),
            disagreements=(),
        ),
        prompt="p",
        allowed_evidence_ids=("document:abc",),
    )

    report = CouncilEvidenceService().build(review)

    assert report.claims[0]["evidence_ids"] == []
    assert report.claims[0]["supported"] is False
    assert report.invalid_evidence_references == ("qwen:invented:42",)
    assert report.requires_human_review is True


def test_known_evidence_id_is_preserved() -> None:
    response = ModelResponse(
        provider="kimi",
        model="test",
        text='{"claims":[{"topic":"date","statement":"Дата 13 августа","position":"supports","evidence_ids":["document:abc"]}],"missing_evidence":[],"lawyer_questions":[]}',
        metadata={},
    )
    review = CouncilReview(
        council=CouncilResult(
            responses=(response,),
            failed_providers=(),
            disagreements=(),
        ),
        prompt="p",
        allowed_evidence_ids=("document:abc",),
    )

    report = CouncilEvidenceService().build(review)

    assert report.claims[0]["evidence_ids"] == ["document:abc"]
    assert report.claims[0]["supported"] is True
    assert report.invalid_evidence_references == ()
