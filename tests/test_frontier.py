import pytest


@pytest.mark.frontier
def test_malformed_login_json_is_rejected(client):
    response = client.post(
        "/api/v2/login",
        headers={"Content-Type": "application/json"},
        content=b"{not-json",
    )

    assert response.status_code in {400, 422}


@pytest.mark.frontier
def test_login_rejects_oversized_organization(client):
    organization = "x" * 1001
    response = client.post(
        "/api/v2/login",
        headers={"ngc_key": "invalid-key"},
        json={"ngc_key": "invalid-key", "ngc_org_name": organization},
    )

    assert response.status_code in {400, 401, 403, 422}


@pytest.mark.frontier
def test_unknown_api_route_returns_not_found(client):
    response = client.get("/api/v2/route-that-does-not-exist")

    assert response.status_code in {401, 404}


@pytest.mark.frontier
def test_unsupported_method_is_rejected(client):
    response = client.put("/api/v2/health")

    assert response.status_code in {405, 404}


@pytest.mark.frontier
def test_path_traversal_org_does_not_escape_route(client):
    response = client.get("/api/v2/orgs/%2e%2e/workspaces")

    assert response.status_code in {400, 401, 403, 404, 422}
