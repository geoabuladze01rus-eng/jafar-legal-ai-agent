from jafar.telegram_fact_check import TelegramLegalFactChecker, source_evidence
from jafar.telegram_publication import FactCheckStatus


class OfficialProvider:
    def verify_claim(self, claim: str):
        return [
            source_evidence(
                title="Верховный Суд Российской Федерации",
                url="https://vsrf.ru/documents/example",
                verified=True,
            )
        ]


class MediaOnlyProvider:
    def verify_claim(self, claim: str):
        return [
            source_evidence(
                title="Профессиональное СМИ",
                url="https://example.com/legal-news",
                verified=True,
            )
        ]


class BrokenProvider:
    def verify_claim(self, claim: str):
        raise RuntimeError("provider unavailable")


def test_official_source_verifies_claim() -> None:
    result = TelegramLegalFactChecker(OfficialProvider()).check(["Правовой тезис"])
    assert result.status is FactCheckStatus.VERIFIED


def test_media_only_source_cannot_verify_legal_claim() -> None:
    result = TelegramLegalFactChecker(MediaOnlyProvider()).check(["Правовой тезис"])
    assert result.status is FactCheckStatus.UNVERIFIED


def test_empty_claim_set_fails_closed() -> None:
    result = TelegramLegalFactChecker(OfficialProvider()).check([])
    assert result.status is FactCheckStatus.UNVERIFIED


def test_provider_failure_fails_closed_without_leaking_error_message() -> None:
    result = TelegramLegalFactChecker(BrokenProvider()).check(["Правовой тезис"])
    assert result.status is FactCheckStatus.FAILED
    assert result.notes == "Fact-check provider failed: RuntimeError"
