"""HTTP client for the local Ultralytics execution adapter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx


class UltralyticsAdapterError(RuntimeError):
    """Safe adapter error without credentials."""


class UltralyticsClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or os.getenv("TAO_ULTRALYTICS_URL", "http://127.0.0.1:9200")).rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text[:500])
            except ValueError:
                detail = response.text[:500]
            raise UltralyticsAdapterError(f"Ultralytics adapter HTTP {response.status_code}: {detail}")
        return response.json() if response.content else None

    def health(self) -> Any:
        return self.request("GET", "/health")

    def jobs(self) -> Any:
        return self.request("GET", "/v1/jobs")

    def job(self, job_id: str) -> Any:
        return self.request("GET", f"/v1/jobs/{job_id}")

    def models(self) -> Any:
        return self.request("GET", "/v1/models")

    def submit_train(self, payload: dict[str, Any]) -> Any:
        return self.request("POST", "/v1/jobs/train", json=payload)

    def evaluate(self, job_id: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", f"/v1/jobs/{job_id}/evaluate", json=payload)

    def export(self, job_id: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", f"/v1/jobs/{job_id}/export", json=payload)

    def infer_image(self, model_name: str, image_path: str) -> Any:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(image_path)
        with path.open("rb") as image:
            return self.request("POST", "/v1/infer/image", data={"model_name": model_name}, files={"file": (path.name, image, "application/octet-stream")})
