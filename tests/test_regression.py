import pytest


@pytest.mark.auth
def test_authenticated_workspaces_endpoint_is_stable(client, auth_headers, authenticated_url):
    response = client.get(
        f"{authenticated_url}/workspaces",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), (dict, list))


@pytest.mark.auth
def test_job_schema_endpoint_is_stable(client, auth_headers, authenticated_url):
    response = client.get(
        f"{authenticated_url}/jobs:schema",
        headers=auth_headers,
        params={"network_arch": "classification_pyt", "action": "train"},
    )

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


@pytest.mark.auth
def test_base_experiment_listing_is_stable(client, auth_headers, authenticated_url):
    response = client.get(
        f"{authenticated_url}/jobs:list_base_experiments",
        headers=auth_headers,
        params={"network_arch": "classification_pyt"},
    )

    assert response.status_code == 200
    assert isinstance(response.json(), (dict, list))


@pytest.mark.auth
def test_job_collection_does_not_require_gpu_to_list(client, auth_headers, authenticated_url):
    response = client.get(
        f"{authenticated_url}/jobs",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), (dict, list))
