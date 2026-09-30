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

## Mutations

Read-only tools are enabled by default. Workspace creation/deletion require:

```bash
export TAO_MCP_ALLOW_MUTATIONS=true
```

They also require `confirm="I_CONFIRM"` in the tool call.

## Tests

```bash
make mcp-test
```
