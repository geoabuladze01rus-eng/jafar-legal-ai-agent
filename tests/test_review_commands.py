from jafar.review_commands import ReviewAction, parse_review_command


def test_parse_approve_command():
    command = parse_review_command("/review approve 42")
    assert command is not None
    assert command.action == ReviewAction.APPROVE
    assert command.queue_id == 42


def test_parse_reject_command():
    command = parse_review_command("/review reject 7")
    assert command is not None
    assert command.action == ReviewAction.REJECT
    assert command.queue_id == 7


def test_invalid_command_is_ignored():
    assert parse_review_command("/review maybe 7") is None
    assert parse_review_command("hello") is None
