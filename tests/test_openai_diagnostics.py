import urllib.error

from jafar.openai_diagnostics import classify_openai_failure


def test_openai_failure_categories_are_safe():
    assert classify_openai_failure(status=401) == "AUTHENTICATION"
    assert classify_openai_failure(status=403) == "AUTHENTICATION"
    assert classify_openai_failure(status=404) == "MODEL_UNAVAILABLE"
    assert classify_openai_failure(status=429) == "RATE_LIMIT"
    assert classify_openai_failure(status=400) == "INVALID_REQUEST"
    assert classify_openai_failure(status=500) == "PROVIDER_ERROR"
    assert classify_openai_failure(response_shape_valid=False) == "INVALID_RESPONSE"
    assert classify_openai_failure(error=TimeoutError()) == "TIMEOUT"
    assert classify_openai_failure(error=urllib.error.URLError("offline")) == "NETWORK"
