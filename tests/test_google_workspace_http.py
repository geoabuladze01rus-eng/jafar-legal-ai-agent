import httpx
import pytest

from jafar.google_workspace_http import (
    GoogleHTTPClient,
    GoogleWorkspaceAPIError,
    GoogleWorkspaceAuthRequiredError,
    GoogleWorkspaceNetworkError,
)


def make_client(handler):
    return GoogleHTTPClient(
        access_token="access-token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_missing_access_token_is_the_only_local_auth_required_condition():
    client = GoogleHTTPClient(access_token=None, client=httpx.Client(transport=httpx.MockTransport(lambda _: None)))

    with pytest.raises(GoogleWorkspaceAuthRequiredError):
        client.get("https://google.test/resource")


@pytest.mark.parametrize(
    ("reason", "expected_kind"),
    [
        ("accessNotConfigured", "api_disabled"),
        ("insufficientPermissions", "insufficient_scope"),
        ("ACCESS_TOKEN_SCOPE_INSUFFICIENT", "insufficient_scope"),
    ],
)
def test_google_api_errors_are_not_masked_as_oauth_required(reason, expected_kind):
    def handler(_request):
        return httpx.Response(403, json={"error": {"errors": [{"reason": reason}]}})

    with pytest.raises(GoogleWorkspaceAPIError) as raised:
        make_client(handler).get("https://google.test/resource")

    assert raised.value.status_code == 403
    assert raised.value.kind == expected_kind


def test_google_network_error_is_not_masked_as_oauth_required():
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(GoogleWorkspaceNetworkError):
        make_client(handler).get("https://google.test/resource")


def test_google_unauthorized_response_requires_reauthorization():
    def handler(_request):
        return httpx.Response(401, json={"error": {"status": "UNAUTHENTICATED"}})

    with pytest.raises(GoogleWorkspaceAuthRequiredError):
        make_client(handler).get("https://google.test/resource")
