"""Small, authenticated client for the TAO FTMS v2 API."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


class TaoAPIError(RuntimeError):
    """Safe API error that never includes credentials."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"TAO API returned HTTP {status_code}: {message}")


def _safe_message(response: httpx.Response) -> str:
    try:
        body: Any = response.json()
        if isinstance(body, dict):
            message = body.get("error_desc") or body.get("message") or body
        else:
            message = body
    except ValueError:
        message = response.text[:500]
    return re.sub(r"(nvapi-|Bearer\s+)[^\s\"']+", "[REDACTED]", str(message))


class TaoClient:
    """Authenticated FTMS client with an in-memory JWT."""

    def __init__(
        self,
        base_url: str | None = None,
        org: str | None = None,
        ngc_key: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = (base_url or os.getenv("TAO_BASE_URL", "http://localhost:8090")).rstrip("/")
        self.org = org or os.getenv("TAO_ORG", "getter")
        self.ngc_key = ngc_key if ngc_key is not None else os.getenv("NGC_KEY", "")
        self.token = token if token is not None else os.getenv("TAO_TOKEN", "")
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    def close(self) -> None:
        self._http.close()

    def _login(self) -> str:
        if not self.ngc_key:
            raise TaoAPIError(401, "Set TAO_TOKEN or NGC_KEY in the MCP environment")
        response = self._http.post(
            "/api/v2/login",
            headers={"ngc_key": self.ngc_key},
            json={
                "ngc_key": self.ngc_key,
                "ngc_org_name": self.org,
                "enable_telemetry": False,
            },
        )
        if response.status_code != 200:
            raise TaoAPIError(response.status_code, _safe_message(response))
        self.token = response.json().get("token", "")
        if not self.token:
            raise TaoAPIError(502, "TAO login response did not contain a token")
        return self.token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token or self._login()}"}

    def request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        headers = self._headers() if authenticated else {}
        response = self._http.request(method, path, headers=headers, params=params, json=json_body)
        if response.status_code == 401 and authenticated and self.ngc_key:
            self.token = ""
            response = self._http.request(
                method,
                path,
                headers=self._headers(),
                params=params,
                json=json_body,
            )
        if response.status_code >= 400:
            raise TaoAPIError(response.status_code, _safe_message(response))
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            # The logs endpoint may return plain text or an empty-looking stream.
            return response.text

    def health(self) -> Any:
        return self.request("GET", "/api/v2/health", authenticated=False)

    def openapi(self) -> Any:
        return self.request("GET", "/api/v2/openapi.json", authenticated=False)

    def workspaces(self) -> Any:
        return self.request("GET", f"/api/v2/orgs/{self.org}/workspaces")

    def workspace(self, workspace_id: str) -> Any:
        return self.request("GET", f"/api/v2/orgs/{self.org}/workspaces/{workspace_id}")

    def datasets(self) -> Any:
        return self.request("GET", f"/api/v2/orgs/{self.org}/datasets")

    def jobs(self) -> Any:
        return self.request("GET", f"/api/v2/orgs/{self.org}/jobs")

    def job(self, job_id: str) -> Any:
        return self.request("GET", f"/api/v2/orgs/{self.org}/jobs/{job_id}")

    def job_logs(self, job_id: str) -> Any:
        return self.request("GET", f"/api/v2/orgs/{self.org}/jobs/{job_id}:logs")

    def job_schema(self, network_arch: str, action: str) -> Any:
        return self.request(
            "GET",
            f"/api/v2/orgs/{self.org}/jobs:schema",
            params={"network_arch": network_arch, "action": action},
        )

    def base_experiments(self, network_arch: str | None = None) -> Any:
        params = {"network_arch": network_arch} if network_arch else None
        return self.request(
            "GET",
            f"/api/v2/orgs/{self.org}/jobs:list_base_experiments",
            params=params,
        )

    def gpu_types(self) -> Any:
        return self.request("GET", f"/api/v2/orgs/{self.org}/jobs:gpu_types")

    def create_job(
        self,
        *,
        name: str,
        network_arch: str,
        action: str,
        workspace_id: str,
        specs: dict[str, Any],
        parent_job_id: str | None = None,
        train_dataset_uris: list[str] | None = None,
        eval_dataset_uri: str | None = None,
        inference_dataset_uri: str | None = None,
        base_experiment_ids: list[str] | None = None,
    ) -> Any:
        payload: dict[str, Any] = {
            "kind": "experiment",
            "name": name,
            "network_arch": network_arch,
            "encryption_key": os.getenv("TAO_ENCRYPTION_KEY", "tlt_encode"),
            "workspace": workspace_id,
            "action": action,
            "specs": specs,
        }
        if parent_job_id:
            payload["parent_job_id"] = parent_job_id
        if train_dataset_uris:
            payload["train_dataset_uris"] = train_dataset_uris
        if eval_dataset_uri:
            payload["eval_dataset_uri"] = eval_dataset_uri
        if inference_dataset_uri:
            payload["inference_dataset_uri"] = inference_dataset_uri
        if base_experiment_ids:
            payload["base_experiment_ids"] = base_experiment_ids
        return self.request("POST", f"/api/v2/orgs/{self.org}/jobs", json_body=payload)

    def cancel_job(self, job_id: str) -> Any:
        return self.request("POST", f"/api/v2/orgs/{self.org}/jobs/{job_id}:cancel")

    def create_workspace(self, name: str) -> Any:
        return self.request(
            "POST",
            f"/api/v2/orgs/{self.org}/workspaces",
            json_body={
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
            },
        )

    def delete_workspace(self, workspace_id: str) -> Any:
        return self.request("DELETE", f"/api/v2/orgs/{self.org}/workspaces/{workspace_id}")
