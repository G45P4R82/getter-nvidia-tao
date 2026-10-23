"""Ultralytics/YOLO adapter controlled alongside TAO FTMS."""

from __future__ import annotations

import json
import base64
import os
import csv
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field


app = FastAPI(title="TAO Ultralytics Adapter", version="0.1.0")
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.RLock()
_execution_lock = threading.Lock()


def _path_env(name: str, default: str) -> Path:
    path = Path(os.getenv(name, default)).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


MODEL_ROOT = _path_env("ULTRALYTICS_MODEL_ROOT", ".tao-ultralytics/models")
JOB_ROOT = _path_env("ULTRALYTICS_JOB_ROOT", ".tao-ultralytics/jobs")
DATA_ROOT = _path_env("ULTRALYTICS_DATA_ROOT", ".tao-ultralytics/shared")
JOBS_FILE = JOB_ROOT / "jobs.json"
CATALOG_FILE = Path(os.getenv("ULTRALYTICS_MODEL_CATALOG", str(MODEL_ROOT / "models.json")))


class TrainRequest(BaseModel):
    model_name: str = Field(min_length=1, max_length=100)
    architecture: str = Field(default="yolo26n", min_length=1, max_length=100)
    dataset_path: str | None = None
    dataset_uri: str | None = None
    tao_workspace_id: str | None = None
    tao_dataset_id: str | None = None
    input_size: int = Field(default=640, ge=32, le=4096)
    max_epochs: int = Field(default=1, ge=1, le=10000)
    batch_size: int = Field(default=4, ge=1, le=4096)
    patience: int = Field(default=20, ge=1, le=10000)
    device: str = "0"
    train: dict[str, Any] = Field(default_factory=dict)


class ActionRequest(BaseModel):
    dataset_path: str | None = None
    dataset_uri: str | None = None
    input_size: int = Field(default=640, ge=32, le=4096)
    device: str = "0"


def _save_jobs() -> None:
    temporary = JOBS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(_jobs, ensure_ascii=True, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(JOBS_FILE)


def _set_job(job_id: str, **changes: Any) -> None:
    with _jobs_lock:
        _jobs[job_id].update(changes)
        _save_jobs()


def _load_jobs() -> None:
    if not JOBS_FILE.exists():
        return
    try:
        loaded = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            _jobs.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass


def _download_s3_dataset(dataset_uri: str, destination: Path) -> Path:
    import boto3

    bucket, prefix = dataset_uri.removeprefix("seaweedfs://").split("/", 1)
    client = boto3.client(
        "s3",
        endpoint_url=os.getenv("TAO_SEAWEEDFS_ENDPOINT", "http://seaweedfs-s3:18333"),
        aws_access_key_id=os.getenv("TAO_SEAWEEDFS_ACCESS_KEY", "seaweedfs"),
        aws_secret_access_key=os.getenv("TAO_SEAWEEDFS_SECRET_KEY", "seaweedfs123"),
        region_name=os.getenv("TAO_SEAWEEDFS_REGION", "us-east-1"),
    )
    destination.mkdir(parents=True, exist_ok=True)
    paginator = client.get_paginator("list_objects_v2")
    found = False
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix.rstrip("/") + "/"):
        for item in page.get("Contents", []):
            key = item["Key"]
            relative = key[len(prefix.rstrip("/")):].lstrip("/")
            if not relative:
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(target))
            found = True
    if not found:
        raise FileNotFoundError(f"No objects found for {dataset_uri}")
    return destination / "data.yaml"


def _resolve_dataset(dataset_path: str | None, dataset_uri: str | None, download_dir: Path | None = None) -> Path:
    if dataset_path:
        candidate = Path(dataset_path).expanduser()
    elif dataset_uri and dataset_uri.startswith("seaweedfs://"):
        relative = dataset_uri.removeprefix("seaweedfs://").split("/", 1)[-1]
        candidate = DATA_ROOT / relative
        if not candidate.exists():
            if download_dir is None:
                raise HTTPException(status_code=404, detail=f"SeaweedFS dataset is not mounted: {dataset_uri}")
            return _download_s3_dataset(dataset_uri, download_dir / "dataset")
    else:
        raise HTTPException(status_code=400, detail="dataset_path or seaweedfs dataset_uri is required")
    if candidate.is_file() and candidate.name == "data.yaml":
        return candidate
    data_yaml = candidate / "data.yaml"
    if not data_yaml.exists():
        raise HTTPException(status_code=404, detail=f"YOLO data.yaml not found: {data_yaml}")
    return data_yaml


def _model_dir(model_name: str) -> Path:
    path = MODEL_ROOT / model_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_data_yaml(data_yaml: Path, job_dir: Path) -> Path:
    """Make relative YOLO dataset paths independent of the container cwd."""
    import yaml

    config = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    configured_root = config.get("path", ".")
    root = Path(configured_root)
    if root.is_absolute() and root.exists():
        root = root.resolve()
    else:
        root = (data_yaml.parent / root).resolve() if not root.is_absolute() else data_yaml.parent.resolve()
    config["path"] = str(root)
    normalized = job_dir / "data.yaml"
    normalized.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return normalized


def _metrics_from_run(run_dir: Path) -> list[dict[str, Any]]:
    csv_path = run_dir / "results.csv"
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as stream:
        return [{key.strip(): value.strip() for key, value in row.items()} for row in csv.DictReader(stream)]


def _next_version(model_name: str) -> str:
    if not CATALOG_FILE.exists():
        return "v1"
    try:
        catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
        versions = catalog.get("models", {}).get(model_name, {}).get("versions", [])
        numbers = [int(str(item.get("version", "")).removeprefix("v")) for item in versions if str(item.get("version", "")).removeprefix("v").isdigit()]
        return f"v{max(numbers, default=0) + 1}"
    except (OSError, ValueError, json.JSONDecodeError):
        return "v1"


def _register_model(job: dict[str, Any], best_path: Path) -> dict[str, Any]:
    version = _next_version(job["model_name"])
    record = {
        "model_name": job["model_name"],
        "version": version,
        "backend": "ultralytics",
        "architecture": job["architecture"],
        "adapter_job_id": job["id"],
        "artifact_path": str(best_path),
        "tao_workspace_id": job.get("tao_workspace_id"),
        "tao_dataset_id": job.get("tao_dataset_id"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    catalog: dict[str, Any] = {"models": {}}
    if CATALOG_FILE.exists():
        try:
            catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    entry = catalog.setdefault("models", {}).setdefault(job["model_name"], {"model_name": job["model_name"], "versions": []})
    entry["versions"].append(record)
    CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_FILE.write_text(json.dumps(catalog, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return record


def _run_train(job_id: str, request: TrainRequest) -> None:
    with _execution_lock:
        try:
            from ultralytics import YOLO

            job_dir = JOB_ROOT / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            data_yaml = _resolve_dataset(request.dataset_path, request.dataset_uri, job_dir)
            data_yaml = _normalize_data_yaml(data_yaml, job_dir)
            _set_job(job_id, status="running", data_yaml=str(data_yaml))
            model = YOLO(request.architecture if request.architecture.endswith(".pt") else f"{request.architecture}.pt")
            train_args = dict(request.train)
            train_args.update({"data": str(data_yaml), "project": str(job_dir), "name": "train", "exist_ok": True})
            train_args.setdefault("epochs", request.max_epochs)
            train_args.setdefault("imgsz", request.input_size)
            train_args.setdefault("batch", request.batch_size)
            train_args.setdefault("patience", request.patience)
            train_args.setdefault("device", request.device)
            train_args.setdefault("workers", int(os.getenv("YOLO_WORKERS", "1")))
            results = model.train(**train_args)
            source_best = Path(getattr(results, "save_dir", job_dir)) / "weights" / "best.pt"
            if not source_best.exists():
                raise RuntimeError(f"Ultralytics did not produce best.pt: {source_best}")
            best_path = _model_dir(request.model_name) / "best.pt"
            shutil.copy2(source_best, best_path)
            record = _register_model(_jobs[job_id], best_path)
            metrics = _metrics_from_run(Path(getattr(results, "save_dir", job_dir)))
            _set_job(job_id, status="done", version=record["version"], artifact_path=str(best_path), metrics=metrics, result=record)
        except Exception as error:
            _set_job(job_id, status="error", error=str(error))


def _run_action(job_id: str, action: str, model_name: str, request: ActionRequest) -> None:
    with _execution_lock:
        try:
            from ultralytics import YOLO

            best = _model_dir(model_name) / "best.pt"
            if not best.exists():
                raise RuntimeError(f"Model artifact not found: {best}")
            model = YOLO(str(best))
            _set_job(job_id, status="running")
            if action == "evaluate":
                action_dir = JOB_ROOT / job_id
                action_dir.mkdir(parents=True, exist_ok=True)
                data_yaml = _resolve_dataset(request.dataset_path, request.dataset_uri, action_dir)
                data_yaml = _normalize_data_yaml(data_yaml, action_dir)
                result = model.val(data=str(data_yaml), imgsz=request.input_size, device=request.device)
                value = getattr(result, "results_dict", {})
            elif action == "export":
                value = model.export(format="onnx", imgsz=request.input_size, device=request.device)
            else:
                raise ValueError(f"Unsupported action: {action}")
            _set_job(job_id, status="done", result=value if isinstance(value, (dict, str, list)) else str(value))
        except Exception as error:
            _set_job(job_id, status="error", error=str(error))


@app.on_event("startup")
def startup() -> None:
    _load_jobs()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": "ultralytics"}


@app.post("/v1/jobs/train", status_code=202)
def submit_train(request: TrainRequest) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    job = {"id": job_id, "action": "train", "status": "queued", **request.model_dump()}
    with _jobs_lock:
        _jobs[job_id] = job
        _save_jobs()
    threading.Thread(target=_run_train, args=(job_id, request), daemon=True).start()
    return {"job_id": job_id, "status": "queued", "backend": "ultralytics", "tao_workspace_id": request.tao_workspace_id, "tao_dataset_id": request.tao_dataset_id}


@app.get("/v1/jobs")
def list_jobs() -> list[dict[str, Any]]:
    with _jobs_lock:
        return list(_jobs.values())


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail="job not found")
        return _jobs[job_id]


@app.get("/v1/jobs/{job_id}/logs")
def get_logs(job_id: str, max_chars: int = 20000) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
    log_path = JOB_ROOT / job_id / "train" / "results.csv"
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    return {"job_id": job_id, "available": bool(text), "text": text[-max_chars:]}


@app.post("/v1/jobs/{job_id}/evaluate", status_code=202)
def evaluate(job_id: str, request: ActionRequest) -> dict[str, Any]:
    with _jobs_lock:
        source = _jobs.get(job_id)
        if not source:
            raise HTTPException(status_code=404, detail="training job not found")
        action_id = str(uuid.uuid4())
        _jobs[action_id] = {"id": action_id, "action": "evaluate", "status": "queued", "model_name": source["model_name"], "parent_job_id": job_id}
        _save_jobs()
    threading.Thread(target=_run_action, args=(action_id, "evaluate", source["model_name"], request), daemon=True).start()
    return {"job_id": action_id, "parent_job_id": job_id, "status": "queued"}


@app.post("/v1/jobs/{job_id}/export", status_code=202)
def export_model(job_id: str, request: ActionRequest) -> dict[str, Any]:
    with _jobs_lock:
        source = _jobs.get(job_id)
        if not source:
            raise HTTPException(status_code=404, detail="training job not found")
        action_id = str(uuid.uuid4())
        _jobs[action_id] = {"id": action_id, "action": "export", "status": "queued", "model_name": source["model_name"], "parent_job_id": job_id}
        _save_jobs()
    threading.Thread(target=_run_action, args=(action_id, "export", source["model_name"], request), daemon=True).start()
    return {"job_id": action_id, "parent_job_id": job_id, "status": "queued"}


@app.get("/v1/models")
def list_models() -> dict[str, Any]:
    if not CATALOG_FILE.exists():
        return {"models": {}}
    try:
        return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"models": {}}


@app.post("/v1/infer/image")
async def infer_image(model_name: str = Form(...), file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        from ultralytics import YOLO

        best = _model_dir(model_name) / "best.pt"
        if not best.exists():
            raise HTTPException(status_code=404, detail="model artifact not found")
        input_path = JOB_ROOT / f"inference-{uuid.uuid4()}-{file.filename or 'image'}"
        input_path.write_bytes(await file.read())
        result_dir = _model_dir(model_name) / "inference"
        YOLO(str(best)).predict(source=str(input_path), save=True, project=str(result_dir), name="latest", exist_ok=True)
        output_files = [path for path in (result_dir / "latest").glob("*") if path.is_file()]
        if not output_files:
            raise RuntimeError("Ultralytics did not produce an inference image")
        output_path = max(output_files, key=lambda path: path.stat().st_mtime)
        return {
            "model_name": model_name,
            "output_path": str(output_path),
            "output_dir": str(result_dir / "latest"),
            "image_base64": base64.b64encode(output_path.read_bytes()).decode("ascii"),
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
