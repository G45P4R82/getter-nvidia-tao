def test_health_is_ready(client):
    response = client.get("/api/v2/health")

    assert response.status_code == 200
    assert set(response.json()) >= {"liveness", "readiness"}


def test_openapi_contract_is_available(client):
    response = client.get("/api/v2/openapi.json")

    assert response.status_code == 200
    document = response.json()
    assert document["info"]["title"] == "NVIDIA TAO API v2"
    assert "/api/v2/login" in document["paths"]
    assert "/api/v2/orgs/{org_name}/jobs" in document["paths"]


def test_redoc_is_available(client):
    response = client.get("/api/v2/redoc")

    assert response.status_code == 200
    assert "redoc" in response.text.lower()


def test_root_is_not_used_as_health_endpoint(client):
    response = client.get("/")

    assert response.status_code in {404, 405}
