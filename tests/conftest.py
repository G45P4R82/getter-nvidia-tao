import os
from dataclasses import dataclass

import httpx
import pytest


@dataclass(frozen=True)
class Settings:
    base_url: str
    org: str
    ngc_key: str
    token: str
    run_auth: bool
    run_integration: bool


def pytest_addoption(parser):
    parser.addoption(
        "--run-auth",
        action="store_true",
        help="run tests that authenticate against NGC",
    )
    parser.addoption(
        "--run-integration",
        action="store_true",
        help="run tests that create and delete TAO resources",
    )


@pytest.fixture(scope="session")
def settings(pytestconfig):
    return Settings(
        base_url=os.getenv("TAO_BASE_URL", "http://localhost:8090").rstrip("/"),
        org=os.getenv("TAO_ORG", "getter"),
        ngc_key=os.getenv("NGC_KEY", ""),
        token=os.getenv("TAO_TOKEN", ""),
        run_auth=pytestconfig.getoption("--run-auth") or bool(os.getenv("NGC_KEY")),
        run_integration=pytestconfig.getoption("--run-integration"),
    )


@pytest.fixture(scope="session")
def client(settings):
    with httpx.Client(base_url=settings.base_url, timeout=20.0) as api_client:
        yield api_client


@pytest.fixture(scope="session")
def auth_headers(client, settings):
    if settings.token:
        return {"Authorization": f"Bearer {settings.token}"}

    if not settings.run_auth or not settings.ngc_key:
        pytest.skip("set NGC_KEY or TAO_TOKEN to run authenticated tests")

    response = client.post(
        "/api/v2/login",
        headers={"ngc_key": settings.ngc_key},
        json={
            "ngc_key": settings.ngc_key,
            "ngc_org_name": settings.org,
            "enable_telemetry": False,
        },
    )
    assert response.status_code == 200, "TAO login failed without exposing credentials"
    token = response.json().get("token")
    assert token, "TAO login response did not contain a token"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def authenticated_url(settings):
    return f"/api/v2/orgs/{settings.org}"
