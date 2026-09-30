import httpx
import pytest
import respx

from tao_mcp.client import TaoAPIError, TaoClient


@respx.mock
def test_login_and_authenticated_request():
    respx.post("http://tao.test/api/v2/login").mock(
        return_value=httpx.Response(200, json={"token": "jwt-token"})
    )
    workspaces = respx.get("http://tao.test/api/v2/orgs/getter/workspaces").mock(
        return_value=httpx.Response(200, json={"workspaces": []})
    )

    client = TaoClient(base_url="http://tao.test", org="getter", ngc_key="ngc-test")
    assert client.workspaces() == {"workspaces": []}
    assert workspaces.calls[0].request.headers["Authorization"] == "Bearer jwt-token"
    client.close()


@respx.mock
def test_api_error_redacts_token():
    respx.get("http://tao.test/api/v2/orgs/getter/workspaces").mock(
        return_value=httpx.Response(401, json={"error_desc": "Bearer secret-token"})
    )
    client = TaoClient(base_url="http://tao.test", token="jwt-token")
    with pytest.raises(TaoAPIError, match="REDACTED"):
        client.workspaces()
    client.close()
