from jafar.legal_holding_verifier import HoldingStatus, LegalHoldingVerifier
from jafar.legal_proposition_extractor import PropositionCandidate


def candidate(text: str) -> PropositionCandidate:
    return PropositionCandidate(text=text, confidence=0.55, rationale="test")


def test_accepts_explicit_court_holding() -> None:
    result = LegalHoldingVerifier().verify(
        candidate("Судебная коллегия указала, что доказательство, полученное с нарушением закона, не может быть признано допустимым.")
    )
    assert result.status == HoldingStatus.VERIFIED_HOLDING
    assert result.may_enter_holding_base is True


def test_rejects_party_argument() -> None:
    result = LegalHoldingVerifier().verify(
        candidate("Защитник указал, что суд пришел к выводу без исследования существенных обстоятельств дела.")
    )
    assert result.status == HoldingStatus.PARTY_ARGUMENT
    assert result.may_enter_holding_base is False


def test_rejects_lower_court_position() -> None:
    result = LegalHoldingVerifier().verify(
        candidate("Суд первой инстанции указал, что доказательства являются допустимыми и достаточными для вывода.")
    )
    assert result.status == HoldingStatus.LOWER_COURT_POSITION


def test_rejects_fact_narrative() -> None:
    result = LegalHoldingVerifier().verify(
        candidate("Из материалов дела следует, что обвиняемый прибыл в учреждение 13 августа и получил билет.")
    )
    assert result.status == HoldingStatus.FACTUAL_NARRATIVE


def test_rejects_quoted_external_authority() -> None:
    result = LegalHoldingVerifier().verify(
        candidate("Как разъяснено в постановлении Пленума, не допускается использование доказательств, полученных с нарушением закона.")
    )
    assert result.status == HoldingStatus.QUOTED_AUTHORITY


def test_ambiguous_reported_speech_requires_review() -> None:
    result = LegalHoldingVerifier().verify(
        candidate("В жалобе заявитель указывает, что Верховный Суд указал на необходимость иной оценки этих обстоятельств.")
    )
    assert result.status == HoldingStatus.REVIEW_REQUIRED
    assert result.may_enter_holding_base is False


def test_accepted_holdings_only_returns_verified() -> None:
    verifier = LegalHoldingVerifier()
    results = verifier.verify_many(
        (
            candidate("Верховный Суд указал, что не допускается произвольное ограничение права на защиту."),
            candidate("Прокурор указал, что вывод суда является законным и обоснованным."),
        )
    )
    accepted = verifier.accepted_holdings(results)
    assert len(accepted) == 1
    assert accepted[0].status == HoldingStatus.VERIFIED_HOLDING
