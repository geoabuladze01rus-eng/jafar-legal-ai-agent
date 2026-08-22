from jafar.fedresurs_adapter import FedresursResponseParser


def test_fedresurs_parser_extracts_message_count():
    data = FedresursResponseParser().parse("Найдено сообщений: 12")
    assert data["message_count"] == 12


def test_fedresurs_parser_does_not_invent_missing_data():
    data = FedresursResponseParser().parse("Данные временно недоступны")
    assert data["message_count"] is None
    assert data["raw_available"] is True
