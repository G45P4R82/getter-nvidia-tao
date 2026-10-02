"""OpenCode-facing FastMCP server for NVIDIA TAO FTMS."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from fastmcp import FastMCP

from tao_mcp.client import TaoClient, TaoAPIError

mcp = FastMCP("tao-ftms")
client = TaoClient()


def _result(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, default=str)


def _validate_id(value: str, field: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", value):
        raise ValueError(f"{field} must be an ID returned by TAO")
    return value


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
def tao_list_gpu_types() -> str:
    """List GPU types available to TAO jobs."""
    return _result(client.gpu_types())


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
def tao_cancel_job(job_id: str, confirm: str = "") -> str:
    """Cancel a running TAO job after explicit confirmation."""
    _require_mutations()
    if confirm != "I_CONFIRM":
        raise PermissionError("Pass confirm='I_CONFIRM' to cancel a TAO job")
    return _result(client.cancel_job(_validate_id(job_id, "job_id")))


if __name__ == "__main__":
    mcp.run()
