from jafar.document_intake import ExtractedPage
from jafar.pavlik_private_e2e import _build_reasoning, extract_motion_contract

MAIN_CASE = "12604008104000012"


def make_pages() -> tuple[ExtractedPage, ...]:
    return (
        ExtractedPage(
            1,
            """
            П О С Т А Н О В Л Е Н И Е
            о возбуждении перед судом ходатайства о продлении меры пресечения
            в виде домашнего ареста
            г. Новороссийск 28 июля 2026 года
            Следователь, рассмотрев материалы уголовного дела № 12604008104000012,
            установил обстоятельства производства.
            """,
        ),
        ExtractedPage(
            2,
            """
            07.07.2026 уголовные дела № 12604008104000018 и № 12604008104000043
            соединены в одном производстве с присвоением номера уголовного дела
            № 12604008104000012.
            Установлено, что в результате организованной преступной деятельности
            Иванова И.И., Петрова П.П., Петрова П.П. в период времени с мая 2022 года
            перемещено более 32 транспортных средств.
            Неуплата таможенных платежей составила 47 556 224,38 рублей.
            Срок предварительного следствия по уголовному делу продлевался,
            последний раз продлен 22.07.2026 на один месяц, то есть до 03.09.2026.
            25.06.2026 в 16 часов 20 минут в порядке закона задержан обвиняемый.
            Допрошенный в тот же день обвиняемый вину в совершении деяния
            признал в полном объеме.
            """,
        ),
        ExtractedPage(
            3,
            """
            27.06.2026 в отношении обвиняемого избрана мера пресечения в виде
            домашнего ареста сроком на 01 месяц 09 суток, то есть до 03.08.2026.
            01.07.2026 обвиняемому предъявлено обвинение, после чего он вину
            в совершении деяния признал в полном объеме.
            Для завершения расследования необходимо продлить срок содержания
            обвиняемого под домашним арестом, то есть до 03.09.2026 включительно.
            В одном из последующих перечислений указана Ивановой А.А.
            Действия были пресечены сотрудниками ПУ ФСБ России по Краснодарскому.
            """,
        ),
        ExtractedPage(
            4,
            """
            ПОСТАНОВИЛ:
            Ходатайствовать перед районным судом о продлении обвиняемому меры
            пресечения в виде домашнего ареста сроком на один месяц,
            то есть до 03.09.2026, с сохранением ограничений.
            """,
        ),
    )


def test_private_motion_contract_extracts_source_grounded_procedural_facts():
    contract = extract_motion_contract(make_pages(), expected_case=MAIN_CASE)

    assert contract.main_case == MAIN_CASE
    assert contract.motion_date == "2026-07-28"
    assert contract.detention_at == "2026-06-25T16:20:00+00:00"
    assert contract.initial_home_arrest_at == "2026-06-27"
    assert contract.initial_home_arrest_until == "2026-08-03"
    assert contract.charge_at == "2026-07-01"
    assert contract.additional_merge_at == "2026-07-07"
    assert contract.investigation_extension_at == "2026-07-22"
    assert contract.investigation_term_until == "2026-09-03"
    assert contract.requested_home_arrest_until == "2026-09-03"
    assert contract.historical_admission_mentions == 2
    assert set(contract.anomaly_codes) == {
        "participant_initials_conflict",
        "duplicate_participant_in_source",
        "truncated_source_sentence",
    }


def test_private_motion_reasoning_never_promotes_request_or_allegation_to_fact():
    contract = extract_motion_contract(make_pages(), expected_case=MAIN_CASE)
    result = _build_reasoning(contract)

    request = next(
        finding
        for finding in result["findings"]
        if finding["metadata"].get("source_type") == "investigation_request"
    )
    allegations = [
        finding
        for finding in result["findings"]
        if finding["metadata"].get("source_type") == "investigation_allegation"
    ]
    historical = next(
        finding
        for finding in result["findings"]
        if finding["metadata"].get("source_type") == "investigation_recorded_statement"
    )

    assert request["metadata"]["is_court_decision"] is False
    assert request["requires_human_review"] is True
    assert allegations
    assert all(finding["requires_human_review"] is True for finding in allegations)
    assert historical["metadata"]["historical_position"] is True
    assert historical["metadata"]["current_position"] is False
    assert len(result["evidence_gaps"]) == 3
