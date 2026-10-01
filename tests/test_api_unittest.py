"""Real TAO FTMS API tests.

Run with TAO_RUN_REAL_TESTS=true. No HTTP responses are mocked.
"""

from __future__ import annotations

import json
import os
import re
import unittest
import uuid

import httpx


def real_tests_enabled() -> bool:
    return os.getenv("TAO_RUN_REAL_TESTS", "false").lower() == "true"


@unittest.skipUnless(real_tests_enabled(), "set TAO_RUN_REAL_TESTS=true")
class RealTaoAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_url = os.getenv("TAO_BASE_URL", "http://localhost:8090").rstrip("/")
        cls.org = os.getenv("TAO_ORG", "getter")
        cls.ngc_key = os.getenv("NGC_KEY", "")
        cls.token = os.getenv("TAO_TOKEN", "")
        cls.client = httpx.Client(base_url=cls.base_url, timeout=60)
        if not cls.token and cls.ngc_key:
            response = cls.client.post(
                "/api/v2/login",
                headers={"ngc_key": cls.ngc_key},
                json={
                    "ngc_key": cls.ngc_key,
                    "ngc_org_name": cls.org,
                    "enable_telemetry": False,
                },
            )
            cls.assertEqual(cls, response.status_code, 200)
            cls.token = response.json()["token"]
        if not cls.token:
            raise unittest.SkipTest("set TAO_TOKEN or NGC_KEY")
        cls.auth = {"Authorization": f"Bearer {cls.token}"}
        cls.prefix = f"/api/v2/orgs/{cls.org}"

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def get(self, path, **kwargs):
        return self.client.get(path, headers=self.auth, **kwargs)

    def test_health_and_openapi(self):
        health = self.client.get("/api/v2/health")
        self.assertEqual(health.status_code, 200)
        self.assertIn("readiness", health.json())

        openapi = self.client.get("/api/v2/openapi.json")
        self.assertEqual(openapi.status_code, 200)
        self.assertIn("/api/v2/login", openapi.json()["paths"])

    def test_workspaces_require_valid_bearer(self):
        no_token = self.client.get(f"{self.prefix}/workspaces")
        invalid_token = self.client.get(
            f"{self.prefix}/workspaces",
            headers={"Authorization": "Bearer invalid-token"},
        )
        self.assertIn(no_token.status_code, (401, 403))
        self.assertIn(invalid_token.status_code, (401, 403))

    def test_workspaces_are_readable_with_valid_bearer(self):
        response = self.get(f"{self.prefix}/workspaces")
        self.assertEqual(response.status_code, 200)

    def test_job_schema_and_gpu_inventory(self):
        schema = self.get(
            f"{self.prefix}/jobs:schema",
            params={"network_arch": "classification_pyt", "action": "train"},
        )
        self.assertEqual(schema.status_code, 200)
        self.assertIsInstance(schema.json(), dict)

        gpu_types = self.get(f"{self.prefix}/jobs:gpu_types")
        self.assertEqual(gpu_types.status_code, 200)

    def test_frontier_inputs_are_rejected(self):
        malformed = self.client.post(
            "/api/v2/login",
            headers={"Content-Type": "application/json"},
            content=b"{not-json",
        )
        self.assertIn(malformed.status_code, (400, 422))

        traversal = self.client.get("/api/v2/orgs/%2e%2e/workspaces")
        self.assertIn(traversal.status_code, (400, 401, 403, 404, 422))

    @unittest.skipUnless(
        os.getenv("TAO_RUN_MUTATIONS", "false").lower() == "true",
        "set TAO_RUN_MUTATIONS=true",
    )
    def test_workspace_real_lifecycle(self):
        name = f"unittest-{uuid.uuid4().hex[:12]}"
        payload = {
            "name": name,
            "shared": False,
            "cloud_type": "seaweedfs",
            "cloud_specific_details": {
                "cloud_type": "seaweedfs",
                "access_key": os.getenv("TAO_SEAWEEDFS_ACCESS_KEY", "seaweedfs"),
                "secret_key": os.getenv("TAO_SEAWEEDFS_SECRET_KEY", "seaweedfs123"),
                "cloud_region": "us-east-1",
                "cloud_bucket_name": "tao-storage",
                "endpoint_url": os.getenv(
                    "TAO_SEAWEEDFS_ENDPOINT", "http://seaweedfs-s3:18333"
                ),
            },
        }
        created_id = None
        try:
            created = self.client.post(
                f"{self.prefix}/workspaces",
                headers=self.auth,
                json=payload,
            )
            self.assertIn(created.status_code, (200, 201))
            created_id = created.json()["id"]
            fetched = self.get(f"{self.prefix}/workspaces/{created_id}")
            self.assertEqual(fetched.status_code, 200)
        finally:
            if created_id:
                deleted = self.client.delete(
                    f"{self.prefix}/workspaces/{created_id}",
                    headers=self.auth,
                )
                self.assertIn(deleted.status_code, (200, 204))


if __name__ == "__main__":
    unittest.main()
