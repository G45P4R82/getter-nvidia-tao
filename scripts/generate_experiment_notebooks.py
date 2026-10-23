#!/usr/bin/env python3
"""Generate the REST notebooks for the remaining TAO experiments."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"


def markdown(title: str, text: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [f"# {title}\n", "\n", text],
    }


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source.splitlines()],
    }


def common_config(experiment: str, full_pipeline: bool) -> str:
    return f'''import copy
import json
import os
import time
import uuid
from pathlib import Path

import requests

TAO_BASE_URL = os.getenv("TAO_BASE_URL", "http://100.107.81.126:8090").rstrip("/")
EXPERIMENT = "{experiment}"
TAO_ORG = os.getenv("TAO_ORG", "getter")
NETWORK_ARCH = os.getenv("TAO_REAL_NETWORK", "classification_pyt")
WORKSPACE_ID = os.getenv("TAO_TEST_WORKSPACE_ID", "98c4bec1-88df-423e-8a15-af78881e9742")
DATASET_URI = os.getenv("TAO_TRAIN_DATASET_URI", "seaweedfs://tao-storage/data/tao-test-classification-v1")
BASE_EXPERIMENT_ID = os.getenv("TAO_BASE_EXPERIMENT_ID", "469f42fe-37dc-55ff-b89b-5096477f9a87")
RUN_EXPERIMENT = os.getenv("RUN_EXPERIMENT_{experiment}", "true").lower() == "true"
EVIDENCE_DIR = Path(os.getenv("TAO_EXPERIMENT_{experiment}_EVIDENCE", "experiment-{experiment}-evidence"))
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

configured = os.getenv("TAO_SECRETS_FILE", "")
candidates = [Path(configured)] if configured else []
candidates += [Path("secrets.json"), Path.cwd() / "secrets.json", Path.cwd().parent / "secrets.json", Path.cwd().parent.parent / "secrets.json", Path("/home/getter/tao-ftms/secrets.json")]
secrets_file = next((path for path in candidates if path.exists()), None)
NGC_KEY = json.loads(secrets_file.read_text(encoding="utf-8"))["ngc_api_key"] if secrets_file else os.getenv("NGC_KEY", os.getenv("TAO_NGC_KEY", ""))
if not NGC_KEY:
    raise RuntimeError("NGC key not found in TAO_SECRETS_FILE, secrets.json, NGC_KEY or TAO_NGC_KEY")

http = requests.Session()
print({{"experiment": "{experiment}", "base_url": TAO_BASE_URL, "run_enabled": RUN_EXPERIMENT, "pipeline": {full_pipeline!r}}})
'''


def api_cell() -> str:
    return '''def api(method, path, payload=None, headers=None, timeout=(5, 30)):
    merged = {"Content-Type": "application/json"}
    if headers:
        merged.update(headers)
    response = http.request(method, TAO_BASE_URL + path, headers=merged, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json() if response.content else None

print("login: starting")
login = api("POST", "/api/v2/login", {"ngc_key": NGC_KEY, "ngc_org_name": TAO_ORG, "enable_telemetry": False}, {"ngc_key": NGC_KEY})
TOKEN = login["token"]
AUTH = {"Authorization": f"Bearer {TOKEN}"}
print("login: PASS")
health = api("GET", "/api/v2/health")
workspace = api("GET", f"/api/v2/orgs/{TAO_ORG}/workspaces/{WORKSPACE_ID}", headers=AUTH)
datasets = api("GET", f"/api/v2/orgs/{TAO_ORG}/datasets", headers=AUTH)
schema = api("GET", f"/api/v2/orgs/{TAO_ORG}/jobs:schema?network_arch={NETWORK_ARCH}&action=train", headers=AUTH)
catalog = api("GET", f"/api/v2/orgs/{TAO_ORG}/jobs:list_base_experiments?network_arch={NETWORK_ARCH}", headers=AUTH)
assert "readiness" in health
assert workspace.get("id") == WORKSPACE_ID
print("context=PASS datasets=", len(datasets.get("datasets", [])), "base_experiments=", len(catalog.get("experiments", [])))
'''


def full_pipeline_cell() -> str:
    return '''def specs_for(action):
    value = copy.deepcopy(schema.get("default", schema))
    value.setdefault("dataset", {})["num_classes"] = int(os.getenv("TAO_NUM_CLASSES", "2"))
    if action in {"export", "gen_trt_engine", "inference"}:
        value["dataset"]["classes_file"] = f"{DATASET_URI.rstrip('/')}/classes.txt"
    if action in {"gen_trt_engine", "inference"}:
        value["dataset"]["batch_size"] = 1
    if action == "train":
        value.setdefault("train", {}).update({"num_epochs": 1, "num_gpus": 1})
    if action == "inference" and isinstance(value.get("inference"), dict):
        value["inference"]["batch_size"] = 1
    return value

def submit(action, parent_job_id=None):
    payload = {
        "kind": "experiment",
        "name": f"experiment-{EXPERIMENT}-{action}-{uuid.uuid4().hex[:12]}",
        "network_arch": NETWORK_ARCH,
        "encryption_key": os.getenv("TAO_ENCRYPTION_KEY", "tlt_encode"),
        "workspace": WORKSPACE_ID,
        "action": action,
        "specs": specs_for(action),
    }
    if parent_job_id:
        payload["parent_job_id"] = parent_job_id
    if action == "train":
        payload.update({"train_dataset_uris": [DATASET_URI], "eval_dataset_uri": DATASET_URI, "inference_dataset_uri": DATASET_URI, "base_experiment_ids": [BASE_EXPERIMENT_ID]})
    elif action == "evaluate":
        payload["eval_dataset_uri"] = os.getenv("TAO_EVAL_DATASET_URI", DATASET_URI)
    elif action == "inference":
        payload["inference_dataset_uri"] = os.getenv("TAO_INFERENCE_DATASET_URI", DATASET_URI)
    submitted = api("POST", f"/api/v2/orgs/{TAO_ORG}/jobs", payload, AUTH)
    (EVIDENCE_DIR / f"{action}-submitted.json").write_text(json.dumps(submitted, indent=2), encoding="utf-8")
    return submitted["id"]

def wait(job_id):
    terminal = {"Done", "Completed", "Error", "Failed", "Failure", "Canceled", "Cancelled"}
    deadline = time.monotonic() + int(os.getenv("TAO_JOB_TIMEOUT_SECONDS", "3600"))
    while time.monotonic() < deadline:
        current = api("GET", f"/api/v2/orgs/{TAO_ORG}/jobs/{job_id}", headers=AUTH)
        (EVIDENCE_DIR / f"{job_id}-status.json").write_text(json.dumps(current, indent=2), encoding="utf-8")
        state = current.get("status")
        print(job_id, state)
        if state in terminal:
            if state not in {"Done", "Completed"}:
                raise RuntimeError(json.dumps(current, indent=2))
            return current
        time.sleep(int(os.getenv("TAO_JOB_POLL_SECONDS", "15")))
    raise TimeoutError(job_id)

if not RUN_EXPERIMENT:
    print("dry-run: nenhum job foi submetido")
else:
    jobs = {}
    jobs["train"] = submit("train")
    wait(jobs["train"])
    jobs["evaluate"] = submit("evaluate", jobs["train"])
    wait(jobs["evaluate"])
    jobs["export"] = submit("export", jobs["train"])
    wait(jobs["export"])
    jobs["gen_trt_engine"] = submit("gen_trt_engine", jobs["export"])
    wait(jobs["gen_trt_engine"])
    jobs["inference"] = submit("inference", jobs["gen_trt_engine"])
    wait(jobs["inference"])
    print(json.dumps({"experiment": EXPERIMENT, "jobs": jobs}, indent=2))
'''


def api_only_cell() -> str:
    return '''print({"health": health, "workspace": workspace.get("id"), "datasets": len(datasets.get("datasets", [])), "base_experiments": len(catalog.get("experiments", []))})
'''


def notebook(number: str, full_pipeline: bool) -> dict:
    title = f"Experimento {number} - " + ("Pipeline completo via API REST" if full_pipeline else "Validacao de API via REST")
    text = "Executa as etapas reais do TAO usando o endpoint Tailscale e salva as respostas em uma pasta de evidencia. Defina RUN_EXPERIMENT_%s=false para dry-run." % number
    cells = [markdown(title, text), {"cell_type": "markdown", "metadata": {}, "source": ["## Configuracao e secrets\n", "\n", "A chave e lida de `secrets.json`/`TAO_SECRETS_FILE`; nenhuma chave e impressa."]}, code(common_config(number, full_pipeline)), code(api_cell())]
    if full_pipeline:
        cells += [{"cell_type": "markdown", "metadata": {}, "source": ["## Execucao real\n", "\n", "O pipeline aguarda cada job ate `Done` antes de iniciar a proxima etapa."]}, code(full_pipeline_cell())]
    else:
        cells += [code(api_only_cell())]
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.12"}}, "nbformat": 4, "nbformat_minor": 5}


def main() -> None:
    for number, full_pipeline in [("001", False), ("002", False), ("008", True), ("009", True), ("010", True), ("011", True), ("012", True)]:
        path = NOTEBOOKS / f"experiment_{number}_curl.ipynb"
        path.write_text(json.dumps(notebook(number, full_pipeline), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
