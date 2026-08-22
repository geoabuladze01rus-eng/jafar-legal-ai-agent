from jafar.comment_response_engine import prepare_response
from jafar.response_safety_gate import evaluate_response


def test_response_engine_contract_reaches_safety_gate():
    draft = prepare_response("что изменилось в законе?")
    result = evaluate_response(draft.intent, draft.decision)
    assert result.allowed is True
    assert result.decision is draft.decision


def test_response_engine_contract_blocks_sensitive_topic():
    draft = prepare_response("сообщение о пытках в колонии")
    result = evaluate_response(draft.intent, draft.decision)
    assert result.allowed is False
