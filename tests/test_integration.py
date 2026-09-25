import uuid

import pytest


@pytest.mark.integration
def test_workspace_lifecycle(client, settings, auth_headers, authenticated_url):
    if not settings.run_integration:
        pytest.skip("pass --run-integration to create and delete a workspace")

    name = f"pytest-{uuid.uuid4().hex[:12]}"
    payload = {
        "name": name,
        "shared": False,
        "cloud_type": "seaweedfs",
        "cloud_specific_details": {
            "cloud_type": "seaweedfs",
            "access_key": "seaweedfs",
            "secret_key": "seaweedfs123",
            "cloud_region": "us-east-1",
            "cloud_bucket_name": "tao-storage",
            "endpoint_url": "http://seaweedfs-s3:18333",
        },
    }

    created_id = None
    try:
        create_response = client.post(
            f"{authenticated_url}/workspaces",
            headers=auth_headers,
            json=payload,
        )
        assert create_response.status_code in {200, 201}
        created_id = create_response.json().get("id")
        assert created_id

        get_response = client.get(
            f"{authenticated_url}/workspaces/{created_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 200
    finally:
        if created_id:
            delete_response = client.delete(
                f"{authenticated_url}/workspaces/{created_id}",
                headers=auth_headers,
            )
            assert delete_response.status_code in {200, 204}
