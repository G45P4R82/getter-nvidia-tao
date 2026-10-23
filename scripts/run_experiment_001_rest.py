#!/usr/bin/env python3
"""Run experiment 001 end-to-end against a local TAO FTMS REST endpoint."""

from __future__ import annotations

import copy
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from tao_mcp.model_catalog import register


BASE_URL = os.getenv("TAO_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
ORG = os.getenv("TAO_ORG", "getter")
WORKSPACE = os.getenv("TAO_TEST_WORKSPACE_ID", "98c4bec1-88df-423e-8a15-af78881e9742")
DATASET = os.getenv(
    "TAO_TRAIN_DATASET_URI",
    "seaweedfs://tao-storage/data/tao-test-classification-v1",
)
EVAL_DATASET = os.getenv("TAO_EVAL_DATASET_URI", DATASET)
INFERENCE_DATASET = os.getenv("TAO_INFERENCE_DATASET_URI", DATASET)
NETWORK = os.getenv("TAO_REAL_NETWORK", "classification_pyt")
MODEL_NAME = os.getenv("TAO_MODEL_NAME", NETWORK)
MODEL_VERSION = os.getenv("TAO_MODEL_VERSION", "v1")
POLL_SECONDS = int(os.getenv("TAO_JOB_POLL_SECONDS", "15"))
TIMEOUT_SECONDS = int(os.getenv("TAO_JOB_TIMEOUT_SECONDS", "3600"))
CATALOG_PATH = os.getenv("TAO_MODEL_CATALOG_PATH", "")


class TaoRest:
    def __init__(self) -> None:
        self.token = ""

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(BASE_URL + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            message = error.read().decode(errors="replace")[:1000]
            raise RuntimeError(f"HTTP {error.code} {method} {path}: {message}") from error
        return json.loads(raw) if raw else None

    def login(self) -> None:
        key = os.getenv("NGC_KEY", "")
        if not key:
            secret_path = Path(os.getenv("TAO_SECRETS_PATH", "/home/getter/tao-ftms/secrets.json"))
            key = json.loads(secret_path.read_text(encoding="utf-8"))["ngc_api_key"]
        response = self.request(
            "POST",
            "/api/v2/login",
            {"ngc_key": key, "ngc_org_name": ORG, "enable_telemetry": False},
        )
        self.token = response["token"]

    def schema(self, action: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"network_arch": NETWORK, "action": action})
        return self.request("GET", f"/api/v2/orgs/{ORG}/jobs:schema?{query}").get("default", {})

    def submit(
        self,
        action: str,
        specs: dict[str, Any],
        parent_job_id: str | None = None,
        train_dataset_uris: list[str] | None = None,
        eval_dataset_uri: str | None = None,
        inference_dataset_uri: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "kind": "experiment",
            "name": f"experiment-001-{action}-{uuid.uuid4().hex[:12]}",
            "network_arch": NETWORK,
            "encryption_key": os.getenv("TAO_ENCRYPTION_KEY", "tlt_encode"),
            "workspace": WORKSPACE,
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
        response = self.request("POST", f"/api/v2/orgs/{ORG}/jobs", payload)
        job_id = response["id"]
        print(
            f"submitted action={action} job_id={job_id} "
            f"name={response.get('name')} status={response.get('status')}",
            flush=True,
        )
        return job_id

    def wait(self, job_id: str) -> dict[str, Any]:
        terminal = {"Done", "Completed", "Error", "Canceled", "Failed"}
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            job = self.request("GET", f"/api/v2/orgs/{ORG}/jobs/{job_id}")
            status = job.get("status")
            print(f"status job_id={job_id} status={status}", flush=True)
            if status in terminal:
                if status not in {"Done", "Completed"}:
                    raise RuntimeError(f"TAO job failed: {job_id} status={status}")
                return job
            time.sleep(POLL_SECONDS)
        raise TimeoutError(f"TAO job did not finish before timeout: {job_id}")


def prepare_specs(client: TaoRest, action: str) -> dict[str, Any]:
    specs = copy.deepcopy(client.schema(action))
    specs.setdefault("dataset", {})["num_classes"] = int(os.getenv("TAO_NUM_CLASSES", "2"))
    if action in {"export", "gen_trt_engine", "inference"}:
        specs["dataset"]["classes_file"] = f"{DATASET.rstrip('/')}/classes.txt"
    if action in {"gen_trt_engine", "inference"}:
        specs["dataset"]["batch_size"] = 1
    if action == "train":
        specs.setdefault("train", {}).update(
            {
                "num_epochs": 1,
                "num_gpus": 1,
                "seed": int(os.getenv("TAO_TRAIN_SEED", "20261006")),
            }
        )
    if action == "inference" and isinstance(specs.get("inference"), dict):
        specs["inference"]["batch_size"] = 1
    return specs


def main() -> int:
    client = TaoRest()
    client.login()
    print("login=ok", flush=True)
    train = client.submit("train", prepare_specs(client, "train"), train_dataset_uris=[DATASET], eval_dataset_uri=EVAL_DATASET, inference_dataset_uri=INFERENCE_DATASET)
    train_result = client.wait(train)
    previous_catalog = os.environ.get("TAO_MODEL_CATALOG_PATH")
    if CATALOG_PATH:
        os.environ["TAO_MODEL_CATALOG_PATH"] = CATALOG_PATH
    model = register({
        "model_name": MODEL_NAME,
        "version": MODEL_VERSION,
        "job_id": train,
        "artifact_uri": os.getenv("TAO_MODEL_ARTIFACT_URI", ""),
        "network_arch": NETWORK,
        "status": train_result.get("status"),
        "metadata": {"experiment": "001", "source": "rest"},
    })
    print(f"registered model={model['model_name']} version={model['version']}", flush=True)
    evaluate = client.submit("evaluate", prepare_specs(client, "evaluate"), parent_job_id=model["job_id"], eval_dataset_uri=EVAL_DATASET)
    client.wait(evaluate)
    export = client.submit("export", prepare_specs(client, "export"), parent_job_id=model["job_id"], train_dataset_uris=[DATASET], eval_dataset_uri=EVAL_DATASET)
    export_result = client.wait(export)
    trt = client.submit("gen_trt_engine", prepare_specs(client, "gen_trt_engine"), parent_job_id=export)
    client.wait(trt)
    inference = client.submit("inference", prepare_specs(client, "inference"), parent_job_id=trt, inference_dataset_uri=INFERENCE_DATASET)
    client.wait(inference)
    print(json.dumps({"experiment": "001", "model": model, "jobs": {"train": train, "evaluate": evaluate, "export": export, "gen_trt_engine": trt, "inference": inference}, "export_result_keys": sorted(export_result)}, ensure_ascii=True), flush=True)
    if previous_catalog is not None:
        os.environ["TAO_MODEL_CATALOG_PATH"] = previous_catalog
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
