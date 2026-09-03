from __future__ import annotations

import pytest

from jafar.telegram_polls import TelegramPollStore, validate_poll


def test_quiz_validation_and_pseudonymous_results(tmp_path) -> None:
    poll = validate_poll(
        question="What is next?",
        options=["A", "B", "C"],
        poll_type="quiz",
        correct_option_id=1,
        explanation="B is correct.",
        open_period=60,
    )
    assert poll["correct_option_ids"] == [1]
    store = TelegramPollStore(tmp_path / "polls.sqlite3", identity_secret="s" * 32)
    store.record_sent(
        poll={"id": "poll-1", "question": poll["question"], "options": []},
        chat_id="-1001",
        message_id=44,
    )
    assert store.ingest_update(
        {"poll_answer": {"poll_id": "poll-1", "user": {"id": 101}, "option_ids": [1]}}
    )
    results = store.results("poll-1")
    assert results["message_id"] == 44
    assert results["answer_count"] == 1
    assert len(results["answers"][0]["voter_key"]) == 64
    assert "101" not in str(results)


@pytest.mark.parametrize(
    ("question", "options"),
    [("", ["A"]), ("Question", []), ("Question", ["x" * 101])],
)
def test_invalid_poll_limits_are_rejected(question: str, options: list[str]) -> None:
    with pytest.raises(ValueError):
        validate_poll(question=question, options=options)


def test_unknown_poll_update_is_not_persisted(tmp_path) -> None:
    store = TelegramPollStore(tmp_path / "polls.sqlite3", identity_secret="s" * 32)
    assert not store.ingest_update(
        {"poll_answer": {"poll_id": "unknown", "user": {"id": 101}, "option_ids": [0]}}
    )
