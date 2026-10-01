"""Real TAO training and deployment pipeline tests.

These tests submit real GPU jobs. They are disabled unless explicitly enabled.
"""

from __future__ import annotations

import json
import os
import time
import unittest
from pathlib import Path

import httpx


def pipeline_enabled() -> bool:
    return os.getenv("TAO_RUN_REAL_PIPELINE", "false").lower() == "true"


@unittest.skipUnless(pipeline_enabled(), "set TAO_RUN_REAL_PIPELINE=true")
class RealTaoPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_url = os.getenv("TAO_BASE_URL", "http://localhost:8090").rstrip("/")
        cls.org = os.getenv("TAO_ORG", "getter")
        cls.client = httpx.Client(base_url=cls.base_url, timeout=120)
        cls.token = os.getenv("TAO_TOKEN", "")
        ngc_key = os.getenv("NGC_KEY", "")
        if not cls.token and ngc_key:
            login = cls.client.post(
                "/api/v2/login",
                headers={"ngc_key": ngc_key},
                json={
                    "ngc_key": ngc_key,
                    "ngc_org_name": cls.org,
                    "enable_telemetry": False,
                },
            )
            if login.status_code != 200:
                raise AssertionError(f"TAO login failed with HTTP {login.status_code}")
            cls.token = login.json()["token"]
        if not cls.token:
            raise unittest.SkipTest("set TAO_TOKEN or NGC_KEY")
        cls.headers = {"Authorization": f"Bearer {cls.token}"}
        cls.prefix = f"/api/v2/orgs/{cls.org}"
        cls.workspace_id = os.getenv("TAO_TEST_WORKSPACE_ID", "")
        cls.train_dataset_uri = os.getenv("TAO_TRAIN_DATASET_URI", "")
        if not cls.workspace_id or not cls.train_dataset_uri:
            raise unittest.SkipTest(
                "set TAO_TEST_WORKSPACE_ID and TAO_TRAIN_DATASET_URI"
            )

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    @classmethod
    def _spec(cls, name: str) -> dict:
        raw = os.getenv(name, "")
        file_name = os.getenv(f"{name}_FILE", "")
        if file_name:
            raw = Path(file_name).read_text(encoding="utf-8")
        if not raw:
            raise unittest.SkipTest(f"set {name} or {name}_FILE")
        return json.loads(raw)

    @classmethod
    def _create_job(cls, action: str, specs: dict, parent_job_id: str | None = None):
        network_arch = os.getenv("TAO_REAL_NETWORK", "classification_pyt")
        payload = {
            "kind": "experiment",
            "name": f"unittest-{network_arch}-{action}-{int(time.time())}",
            "network_arch": network_arch,
            "encryption_key": os.getenv("TAO_ENCRYPTION_KEY", "unittest-only"),
            "workspace": cls.workspace_id,
            "action": action,
            "specs": specs,
        }
        if parent_job_id:
            payload["parent_job_id"] = parent_job_id
        else:
            payload["train_dataset_uris"] = [cls.train_dataset_uri]
            payload["eval_dataset_uri"] = os.getenv("TAO_EVAL_DATASET_URI", cls.train_dataset_uri)
            payload["inference_dataset_uri"] = os.getenv(
                "TAO_INFERENCE_DATASET_URI", cls.train_dataset_uri
            )
            base_ids = [x for x in os.getenv("TAO_BASE_EXPERIMENT_IDS", "").split(",") if x]
            if base_ids:
                payload["base_experiment_ids"] = base_ids
        response = cls.client.post(
            f"{cls.prefix}/jobs",
            headers=cls.headers,
            json=payload,
        )
        if response.status_code not in (200, 201):
            raise AssertionError(f"TAO job creation failed: HTTP {response.status_code}")
        job_id = response.json()["id"]
        print(f"created_job action={action} id={job_id}")
        return job_id

    @classmethod
    def _wait_for_job(cls, job_id: str) -> dict:
        terminal = {"Done", "Completed", "Error", "Canceled", "Failed"}
        deadline = time.monotonic() + int(os.getenv("TAO_JOB_TIMEOUT_SECONDS", "3600"))
        last = {}
        while time.monotonic() < deadline:
            response = cls.client.get(
                f"{cls.prefix}/jobs/{job_id}",
                headers=cls.headers,
            )
            if response.status_code != 200:
                raise AssertionError(f"TAO job lookup failed with HTTP {response.status_code}")
            last = response.json()
            print(f"job_status id={job_id} status={last.get('status')}")
            if last.get("status") in terminal:
                break
            time.sleep(int(os.getenv("TAO_JOB_POLL_SECONDS", "15")))
        else:
            cls.fail(f"TAO job did not finish before timeout: {job_id}")
        if last.get("status") in {"Error", "Canceled", "Failed"}:
            raise AssertionError(f"TAO job failed: {last}")
        return last

    def test_real_training_job(self):
        train_job = self._create_job("train", self._spec("TAO_TRAIN_SPECS_JSON"))
        result = self._wait_for_job(train_job)
        self.assertIn(result.get("status"), {"Done", "Completed"})

    @unittest.skipUnless(
        os.getenv("TAO_RUN_REAL_DEPLOY", "false").lower() == "true",
        "set TAO_RUN_REAL_DEPLOY=true",
    )
    def test_real_evaluate_export_tensorrt_inference(self):
        train_job = self._create_job("train", self._spec("TAO_TRAIN_SPECS_JSON"))
        self._wait_for_job(train_job)
        evaluate = self._create_job(
            "evaluate", self._spec("TAO_EVAL_SPECS_JSON"), train_job
        )
        self._wait_for_job(evaluate)
        export = self._create_job("export", self._spec("TAO_EXPORT_SPECS_JSON"), train_job)
        self._wait_for_job(export)
        trt = self._create_job(
            "gen_trt_engine", self._spec("TAO_TRT_SPECS_JSON"), export
        )
        self._wait_for_job(trt)
        inference = self._create_job(
            "inference", self._spec("TAO_INFERENCE_SPECS_JSON"), trt
        )
        self._wait_for_job(inference)


if __name__ == "__main__":
    unittest.main()
