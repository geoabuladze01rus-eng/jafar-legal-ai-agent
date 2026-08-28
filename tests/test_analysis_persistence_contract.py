from jafar.domains import DocumentTask, MatterType
from jafar.legal_models import AnalysisResponse, LegalAnalysis


def test_analysis_response_is_explicitly_non_persistent_by_default() -> None:
    response = AnalysisResponse(
        analysis=LegalAnalysis(
            task=DocumentTask.LEGAL_ANALYSIS,
            matter_type=MatterType.CRIMINAL,
            summary="Кандидатный анализ",
        ),
        matter_id="matter-1",
    )

    assert response.persisted is False
    assert response.requires_approval_to_persist is True


def test_analysis_persistence_flags_are_serialized_for_clients() -> None:
    payload = AnalysisResponse(
        analysis=LegalAnalysis(
            task=DocumentTask.SUMMARIZE,
            matter_type=MatterType.GENERAL,
            summary="Сводка",
        )
    ).model_dump(mode="json")

    assert payload["persisted"] is False
    assert payload["requires_approval_to_persist"] is True
