import pytest

from jafar.public_source_transport import HttpResponse, SafePublicSourceTransport, TransportPolicy


class FakeClient:
    def __init__(self, response):
        self.response = response

    def get(self, url, *, timeout=10.0):
        return self.response


def test_transport_accepts_public_response():
    transport = SafePublicSourceTransport(
        FakeClient(HttpResponse(200, "ok", "https://example.test"))
    )
    response = transport.get("https://example.test")
    assert response.text == "ok"


def test_transport_rejects_http_error():
    transport = SafePublicSourceTransport(
        FakeClient(HttpResponse(403, "forbidden", "https://example.test"))
    )
    with pytest.raises(RuntimeError):
        transport.get("https://example.test")


def test_transport_rejects_oversized_response():
    transport = SafePublicSourceTransport(
        FakeClient(HttpResponse(200, "12345", "https://example.test")),
        TransportPolicy(max_response_bytes=4),
    )
    with pytest.raises(ValueError):
        transport.get("https://example.test")
