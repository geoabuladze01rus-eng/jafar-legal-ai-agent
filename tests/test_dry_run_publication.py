from jafar.dry_run_publication import run_dry_run


def test_dry_run_does_not_call_telegram_and_records_success():
    import asyncio

    result = asyncio.run(run_dry_run())

    assert result["failed"] == []
    assert result["published"] == [(1, 0)]
    assert result["message_id"] == 0
    assert result["sent"][0]["chat_id"] == "@iznanka_ugolovki"
