import pytest


@pytest.mark.auth
def test_login_returns_jwt(client, settings, auth_headers):
    assert auth_headers["Authorization"].startswith("Bearer ")
    assert settings.org


def test_protected_workspaces_require_bearer_token(client, authenticated_url):
    response = client.get(f"{authenticated_url}/workspaces")

    assert response.status_code in {401, 403}


@pytest.mark.frontier
def test_login_without_ngc_header_is_rejected(client, settings):
    response = client.post(
        "/api/v2/login",
        json={"ngc_key": "invalid", "ngc_org_name": settings.org},
    )

    assert response.status_code in {401, 403, 422}


@pytest.mark.frontier
def test_login_with_invalid_key_is_rejected(client, settings):
    response = client.post(
        "/api/v2/login",
        headers={"ngc_key": "invalid-key-for-test"},
        json={"ngc_key": "invalid-key-for-test", "ngc_org_name": settings.org},
    )

    assert response.status_code in {401, 403, 422}


@pytest.mark.frontier
def test_invalid_bearer_token_is_rejected(client, authenticated_url):
    response = client.get(
        f"{authenticated_url}/workspaces",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code in {401, 403}
