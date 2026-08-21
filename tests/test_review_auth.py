from jafar.review_auth import is_owner


def test_owner_id_is_authorized():
    assert is_owner(123, 123) is True


def test_other_user_is_rejected():
    assert is_owner(123, 456) is False


def test_missing_ids_are_rejected():
    assert is_owner(None, 123) is False
    assert is_owner(123, None) is False
