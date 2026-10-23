"""OpenCode-facing FastMCP server for NVIDIA TAO FTMS."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from fastmcp import FastMCP

from tao_mcp.client import TaoClient, TaoAPIError
from tao_mcp.model_catalog import get_version, list_models, next_version, register
from tao_mcp.ultralytics_client import UltralyticsClient

mcp = FastMCP("tao-ftms")
client = TaoClient()
ultralytics = UltralyticsClient()


def _result(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, default=str)


def _validate_id(value: str, field: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", value):
        raise ValueError(f"{field} must be an ID returned by TAO")
    return value


def _find_artifact_uri(value: Any) -> str:
    """Find a useful model/checkpoint URI in a TAO job response when present."""
    preferred_keys = {
        "artifact_uri",
        "checkpoint_uri",
        "model_uri",
        "output_uri",
        "checkpoint_path",
        "model_path",
    }
    if isinstance(value, dict):
        for key in preferred_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
        for child in value.values():
            found = _find_artifact_uri(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_artifact_uri(child)
            if found:
                return found
    return ""


@mcp.tool
def tao_health() -> str:
    """Check TAO FTMS liveness and readiness."""
    return _result(client.health())


@mcp.tool
def tao_api_info() -> str:
    """Return the public TAO API contract summary without authentication."""
    document = client.openapi()
    return _result({"info": document.get("info"), "paths": sorted(document.get("paths", {}))})


@mcp.tool
def tao_list_workspaces() -> str:
    """List workspaces visible in the configured TAO organization."""
    return _result(client.workspaces())


@mcp.tool
def tao_get_workspace(workspace_id: str) -> str:
    """Get one TAO workspace by ID."""
    return _result(client.workspace(_validate_id(workspace_id, "workspace_id")))


@mcp.tool
def tao_list_datasets() -> str:
    """List datasets visible in the configured TAO organization."""
    return _result(client.datasets())


@mcp.tool
def tao_list_jobs() -> str:
    """List TAO jobs visible in the configured organization."""
    return _result(client.jobs())


@mcp.tool
def tao_get_job(job_id: str) -> str:
    """Get metadata for a TAO job by ID."""
    return _result(client.job(_validate_id(job_id, "job_id")))


@mcp.tool
def tao_get_job_logs(job_id: str, max_chars: int = 12000) -> str:
    """Get bounded logs for a TAO job without flooding the model context."""
    if not 1 <= max_chars <= 50000:
        raise ValueError("max_chars must be between 1 and 50000")
    try:
        value = client.job_logs(_validate_id(job_id, "job_id"))
    except TaoAPIError as error:
        if error.status_code == 400 and "not available" in str(error).lower():
            return _result({"available": False, "message": "Logs are not available yet; poll tao_get_job."})
        raise
    text = value if isinstance(value, str) else _result(value)
    return text[-max_chars:]


@mcp.tool
def tao_get_job_schema(network_arch: str, action: str) -> str:
    """Return the validated TAO schema for a model family and action."""
    allowed_actions = {"train", "evaluate", "export", "inference", "gen_trt_engine"}
    if action not in allowed_actions:
        raise ValueError(f"action must be one of: {', '.join(sorted(allowed_actions))}")
    return _result(client.job_schema(network_arch, action))


@mcp.tool
def tao_list_base_experiments(network_arch: str = "") -> str:
    """List available TAO pretrained experiments, optionally by architecture."""
    return _result(client.base_experiments(network_arch or None))


@mcp.tool
def tao_list_models(model_name: str = "") -> str:
    """List locally registered trained models and their versions."""
    return _result({"catalog": "local", "models": list_models(model_name or None)})


@mcp.tool
def tao_get_model_version(model_name: str, version: str) -> str:
    """Get one locally registered trained model version."""
    try:
        return _result(get_version(model_name, version))
    except KeyError as error:
        raise ValueError(str(error)) from error


@mcp.tool
def tao_list_gpu_types() -> str:
    """List GPU types available to TAO jobs."""
    return _result(client.gpu_types())


@mcp.tool
def tao_ultralytics_health() -> str:
    """Check the YOLO26 Ultralytics execution adapter."""
    return _result(ultralytics.health())


@mcp.tool
def tao_ultralytics_list_jobs() -> str:
    """List jobs executed by the Ultralytics adapter."""
    return _result(ultralytics.jobs())


@mcp.tool
def tao_ultralytics_list_models() -> str:
    """List versioned models registered by the Ultralytics adapter."""
    return _result(ultralytics.models())


@mcp.tool
def tao_ultralytics_get_job(job_id: str) -> str:
    """Get an Ultralytics adapter job by ID."""
    return _result(ultralytics.job(_validate_id(job_id, "job_id")))


@mcp.tool
def tao_get_test_context() -> str:
    """Return the explicitly configured non-secret fixture for real tests."""
    return _result(
        {
            "workspace_id": os.getenv("TAO_TEST_WORKSPACE_ID", ""),
            "train_dataset_uri": os.getenv("TAO_TRAIN_DATASET_URI", ""),
            "eval_dataset_uri": os.getenv("TAO_EVAL_DATASET_URI", ""),
            "inference_dataset_uri": os.getenv("TAO_INFERENCE_DATASET_URI", ""),
            "base_experiment_ids": [
                value
                for value in os.getenv("TAO_BASE_EXPERIMENT_IDS", "").split(",")
                if value
            ],
            "network_arch": os.getenv("TAO_REAL_NETWORK", "classification_pyt"),
        }
    )


@mcp.tool
def tao_ultralytics_submit_train(
    model_name: str,
    dataset_path: str = "",
    dataset_uri: str = "",
    architecture: str = "yolo26n",
    tao_workspace_id: str = "",
    tao_dataset_id: str = "",
    input_size: int = 640,
    max_epochs: int = 1,
    batch_size: int = 4,
    patience: int = 20,
    device: str = "0",
    confirm: str = "",
) -> str:
    """Submit a YOLO26 training job through the Ultralytics adapter."""
    _require_mutations()
    if confirm != "I_CONFIRM":
        raise PermissionError("Pass confirm='I_CONFIRM' to submit an Ultralytics job")
    if not dataset_path and not dataset_uri:
        raise ValueError("dataset_path or dataset_uri is required")
    return _result(
        ultralytics.submit_train(
            {
                "model_name": model_name,
                "architecture": architecture,
                "dataset_path": dataset_path or None,
                "dataset_uri": dataset_uri or None,
                "tao_workspace_id": tao_workspace_id or None,
                "tao_dataset_id": tao_dataset_id or None,
                "input_size": input_size,
                "max_epochs": max_epochs,
                "batch_size": batch_size,
                "patience": patience,
                "device": device,
            }
        )
    )


@mcp.tool
def tao_ultralytics_evaluate(job_id: str, dataset_path: str = "", dataset_uri: str = "", input_size: int = 640, device: str = "0", confirm: str = "") -> str:
    """Evaluate a completed YOLO26 adapter training job."""
    _require_mutations()
    if confirm != "I_CONFIRM":
        raise PermissionError("Pass confirm='I_CONFIRM' to evaluate an Ultralytics job")
    return _result(ultralytics.evaluate(_validate_id(job_id, "job_id"), {"dataset_path": dataset_path or None, "dataset_uri": dataset_uri or None, "input_size": input_size, "device": device}))


@mcp.tool
def tao_ultralytics_export(job_id: str, input_size: int = 640, device: str = "0", confirm: str = "") -> str:
    """Export a trained YOLO26 model to ONNX through the adapter."""
    _require_mutations()
    if confirm != "I_CONFIRM":
        raise PermissionError("Pass confirm='I_CONFIRM' to export an Ultralytics job")
    return _result(ultralytics.export(_validate_id(job_id, "job_id"), {"input_size": input_size, "device": device}))


def _require_mutations() -> None:
    if os.getenv("TAO_MCP_ALLOW_MUTATIONS", "false").lower() != "true":
        raise PermissionError("Mutations are disabled. Set TAO_MCP_ALLOW_MUTATIONS=true explicitly.")


@mcp.tool
def tao_create_workspace(name: str, confirm: str = "") -> str:
    """Create a temporary/local TAO workspace after explicit confirmation."""
    _require_mutations()
    if confirm != "I_CONFIRM":
        raise PermissionError("Pass confirm='I_CONFIRM' to create a workspace")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", name):
        raise ValueError("name must contain 3-64 letters, numbers, '_' or '-'")
    return _result(client.create_workspace(name))


@mcp.tool
def tao_delete_workspace(workspace_id: str, confirm: str = "") -> str:
    """Delete a TAO workspace after explicit confirmation."""
    _require_mutations()
    if confirm != "I_CONFIRM":
        raise PermissionError("Pass confirm='I_CONFIRM' to delete a workspace")
    return _result(client.delete_workspace(_validate_id(workspace_id, "workspace_id")))


@mcp.tool
def tao_submit_job(
    network_arch: str,
    action: str,
    workspace_id: str,
    specs: dict[str, Any],
    confirm: str = "",
    name: str = "",
    parent_job_id: str = "",
    train_dataset_uris: list[str] | None = None,
    eval_dataset_uri: str = "",
    inference_dataset_uri: str = "",
    base_experiment_ids: list[str] | None = None,
    model_name: str = "",
    model_version: str = "",
) -> str:
    """Submit a real TAO job after explicit confirmation and validation."""
    _require_mutations()
    if confirm != "I_CONFIRM":
        raise PermissionError("Pass confirm='I_CONFIRM' to submit a TAO job")
    allowed_actions = {"train", "evaluate", "export", "gen_trt_engine", "inference"}
    if action not in allowed_actions:
        raise ValueError(f"action must be one of: {', '.join(sorted(allowed_actions))}")
    _validate_id(workspace_id, "workspace_id")
    if parent_job_id:
        _validate_id(parent_job_id, "parent_job_id")
    if model_name and not model_version:
        raise ValueError("model_version is required when model_name is provided")
    if model_version and not model_name:
        raise ValueError("model_name is required when model_version is provided")
    if model_name:
        if action == "train":
            raise ValueError("model_name/model_version can only select a model for non-training jobs")
        try:
            model = get_version(model_name, model_version)
        except KeyError as error:
            raise ValueError(str(error)) from error
        registered_job_id = model.get("job_id", "")
        if not registered_job_id:
            raise ValueError("The selected model version has no parent TAO job")
        if parent_job_id and parent_job_id != registered_job_id:
            raise ValueError("parent_job_id conflicts with the selected model version")
        parent_job_id = registered_job_id
    job_name = name or f"mcp-{network_arch}-{action}-{int(time.time())}"
    return _result(
        client.create_job(
            name=job_name,
            network_arch=network_arch,
            action=action,
            workspace_id=workspace_id,
            specs=specs,
            parent_job_id=parent_job_id or None,
            train_dataset_uris=train_dataset_uris,
            eval_dataset_uri=eval_dataset_uri or None,
            inference_dataset_uri=inference_dataset_uri or None,
            base_experiment_ids=base_experiment_ids,
        )
    )


@mcp.tool
def tao_register_model(
    model_name: str,
    job_id: str,
    artifact_uri: str = "",
    version: str = "",
    metadata: dict[str, Any] | None = None,
    confirm: str = "",
) -> str:
    """Register a completed TAO training job as a local versioned model."""
    _require_mutations()
    if confirm != "I_CONFIRM":
        raise PermissionError("Pass confirm='I_CONFIRM' to register a model")
    _validate_id(job_id, "job_id")
    job = client.job(job_id)
    status = str(job.get("status", "")) if isinstance(job, dict) else ""
    if status not in {"Done", "Completed"}:
        raise ValueError(f"Only completed jobs can be registered; current status is {status or 'unknown'}")
    model_version = version or next_version(model_name)
    if not re.fullmatch(r"v?[A-Za-z0-9._-]+", model_version):
        raise ValueError("version must contain only letters, numbers, '.', '_' or '-'")
    record = {
        "model_name": model_name,
        "version": model_version if model_version.startswith("v") else f"v{model_version}",
        "job_id": job_id,
        "artifact_uri": artifact_uri or _find_artifact_uri(job),
        "network_arch": job.get("network_arch", "") if isinstance(job, dict) else "",
        "status": status,
        "metadata": metadata or {},
    }
    try:
        return _result(register(record))
    except KeyError as error:
        raise ValueError(str(error)) from error


@mcp.tool
def tao_cancel_job(job_id: str, confirm: str = "") -> str:
    """Cancel a running TAO job after explicit confirmation."""
    _require_mutations()
    if confirm != "I_CONFIRM":
        raise PermissionError("Pass confirm='I_CONFIRM' to cancel a TAO job")
    return _result(client.cancel_job(_validate_id(job_id, "job_id")))


if __name__ == "__main__":
    mcp.run()
