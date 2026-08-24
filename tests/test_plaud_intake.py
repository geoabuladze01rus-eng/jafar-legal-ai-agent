from datetime import UTC, datetime

from jafar.plaud_intake import PlaudFinding, PlaudIntakeService, PlaudRecording


class FakeAnalyzer:
    def analyze(self, transcript):
        return [
            PlaudFinding(
                kind="potential_deadline",
                text="Постановление обещали подготовить до 25 августа",
                confidence=0.91,
                metadata={"date": "2026-08-25", "requires_confirmation": True},
            )
        ]


def test_plaud_recording_enters_legal_workflow():
    service = PlaudIntakeService(FakeAnalyzer())
    result = service.ingest(
        PlaudRecording(
            recording_id="pl-001",
            title="Разговор со следователем",
            transcript="Постановление обещали подготовить до 25 августа",
            recorded_at=datetime(2026, 8, 21, 10, 0, tzinfo=UTC),
        )
    )
    assert result["recording_id"] == "pl-001"
    assert result["findings"][0]["kind"] == "potential_deadline"
    assert result["findings"][0]["metadata"]["requires_confirmation"] is True
