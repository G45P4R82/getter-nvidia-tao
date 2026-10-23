# TAO FastMCP

Local MCP server for OpenCode and NVIDIA TAO FTMS.

## Run locally

```bash
make mcp-install
mcp/.venv/bin/fastmcp run mcp/src/tao_mcp/server.py:mcp
```

The server uses `stdio`, so OpenCode launches it as a child process. Set the
following variables in the shell that starts OpenCode:

```bash
export TAO_BASE_URL=http://100.107.81.126:8090
export TAO_ORG=getter
export NGC_KEY='...'
```

`TAO_TOKEN` can be used instead of `NGC_KEY` when a valid JWT is already
available. Credentials are not accepted as tool arguments and are never
returned by the MCP.

## Local model catalog

Completed training jobs can be registered as versioned local models. The catalog
is stored at `~/.local/state/tao-mcp/models.json`; override it with
`TAO_MODEL_CATALOG_PATH` for isolated environments or tests.

Register a completed training job with `tao_register_model`, passing
`confirm="I_CONFIRM"`. Use `tao_list_models` and `tao_get_model_version` to
browse the catalog. For evaluation, export, TensorRT generation, or inference,
pass `model_name` and `model_version` to `tao_submit_job`; the registered
training job is then selected as the TAO `parent_job_id`.

The catalog stores the model name, version, training job ID, network architecture,
and artifact URI when TAO returns one. It does not copy model files; the URI must
remain accessible to the configured TAO workspace.

## Ultralytics / YOLO26 adapter

The official TAO catalog does not expose YOLO26 as a native `network_arch`. The
repository therefore includes `ultralytics_adapter/`, a GPU sidecar that keeps
TAO workspace/dataset context while executing YOLO26 through Ultralytics.

Start it with:

```bash
pip install -r ultralytics_adapter/requirements.txt
ULTRALYTICS_DATA_ROOT=/shared-storage \
ULTRALYTICS_MODEL_ROOT=/shared-storage/models \
uvicorn ultralytics_adapter.main:app --host 0.0.0.0 --port 9200
```

Set `TAO_ULTRALYTICS_URL` for the MCP and use the `tao_ultralytics_*` tools.
The first smoke test uses `architecture="yolo26n"`, one GPU, one epoch, and a
YOLO dataset containing `data.yaml`, `images/`, and `labels/`.

## Mutations

Read-only tools are enabled by default. Workspace creation/deletion require:

```bash
export TAO_MCP_ALLOW_MUTATIONS=true
```

They also require `confirm="I_CONFIRM"` in the tool call.

## Tests

```bash
make mcp-real
```

The MCP tests use the real FastMCP server and real FTMS endpoint. Set
`TAO_RUN_REAL_TESTS=true`, `TAO_BASE_URL`, `TAO_ORG`, and either `NGC_KEY` or
`TAO_TOKEN`. No mocked HTTP transport is used.
