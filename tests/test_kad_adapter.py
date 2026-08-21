from jafar.kad_adapter import KadAdapter


def test_kad_parser_extracts_case_count():
    data = KadAdapter.parse_response("Найдено дел: 17")
    assert data["case_count"] == 17


def test_kad_parser_does_not_invent_cases():
    data = KadAdapter.parse_response("Данные временно недоступны")
    assert data["case_count"] == 0
