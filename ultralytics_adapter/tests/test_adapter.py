from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("ULTRALYTICS_DATA_ROOT", tempfile.mkdtemp())
os.environ.setdefault("ULTRALYTICS_MODEL_ROOT", tempfile.mkdtemp())
os.environ.setdefault("ULTRALYTICS_JOB_ROOT", tempfile.mkdtemp())

from fastapi.testclient import TestClient

from ultralytics_adapter.main import TrainRequest, app, _resolve_dataset


class AdapterTests(unittest.TestCase):
    def test_health_reports_ultralytics_backend(self):
        with TestClient(app) as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["backend"], "ultralytics")

    def test_train_request_defaults_to_yolo26n(self):
        request = TrainRequest(model_name="smoke-model", dataset_path="/tmp/dataset")
        self.assertEqual(request.architecture, "yolo26n")
        self.assertEqual(request.max_epochs, 1)

    def test_resolves_dataset_data_yaml(self):
        root = Path(os.environ["ULTRALYTICS_DATA_ROOT"]) / "dataset"
        root.mkdir(parents=True, exist_ok=True)
        (root / "data.yaml").write_text("path: .\ntrain: images/train\n", encoding="utf-8")
        self.assertEqual(_resolve_dataset(None, "seaweedfs://bucket/dataset"), root / "data.yaml")


if __name__ == "__main__":
    unittest.main()
