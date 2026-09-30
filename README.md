# NVIDIA TAO FTMS Docker Compose

Deployment wrapper for the official NVIDIA TAO Finetuning Microservice (FTMS)
using Docker Compose.

This repository does not reimplement TAO. It downloads the official Compose
bundle from `NVIDIA-TAO/tao-tutorials`, applies local configuration, and starts
the official TAO API, workflow, MongoDB, NGINX, and optional SeaweedFS services.

## Requirements

- Linux host with an NVIDIA GPU
- NVIDIA driver and `nvidia-container-toolkit`
- Docker Engine and Docker Compose v2
- An NGC personal API key
- An NGC legacy/PTM key when the selected pretrained models require it

## Quick Start

```bash
cp config.env.example config.env
cp secrets.json.example secrets.json
$EDITOR config.env secrets.json
./tao-ftms up-all
./tao-ftms status
```

The default API endpoint is `http://localhost:8090` and its health endpoint is
`http://localhost:8090/api/v2/health`.

Run the smoke test after the services are up:

```bash
./scripts/smoke-test.sh
```

Stop services without deleting persistent volumes:

```bash
./tao-ftms down
```

## Configuration

`config.env` is intentionally ignored by Git. Start from
`config.env.example` and set the TAO image versions, GPU count, ports, and
storage settings for the host.

`secrets.json` is also ignored by Git. Never commit NGC keys or other secrets.

The upstream bundle supports these modes:

```bash
./tao-ftms up       # TAO API services
./tao-ftms up-all   # API services plus SeaweedFS
./tao-ftms up --airgapped --no-ptm
./tao-ftms logs
./tao-ftms status
./tao-ftms config
```

## API Flow

The FTMS API exposes the core workflow:

```text
login
  -> workspace
  -> dataset
  -> experiment/job
  -> train/evaluate/export/inference
```

The API is served below the configured NGINX port. Consult the upstream TAO
documentation for the exact versioned endpoint contract and authentication
flow.

## Upstream Source

The runtime files are fetched from:

`https://github.com/NVIDIA-TAO/tao-tutorials/tree/main/setup/tao-docker-compose`

Set `UPSTREAM_REF` to a reviewed branch, tag, or commit before a production
deployment. The default is `main` to follow the current official setup.

```bash
UPSTREAM_REF=<reviewed-commit> ./tao-ftms up-all
```

## Production Notes

- Docker Compose is the supported deployment shape for this project.
- Use an external S3-compatible storage instead of SeaweedFS when available.
- Put TLS and network access controls in front of the NGINX endpoint.
- Back up MongoDB and model/data storage independently.
- Pin all image versions and `UPSTREAM_REF` before production use.
- Do not expose MongoDB, SeaweedFS, or Docker socket ports publicly.
- The official FTMS services require Docker access to launch TAO job containers;
  review that trust boundary before exposing the host to untrusted users.

## Ansible Deployment

The checked-in Ansible playbook deploys this repository to a dedicated host
directory and checks ports before it starts anything:

```bash
cp ansible/inventory/group_vars/vault.yml.example \
   ansible/inventory/group_vars/vault.yml
ansible-vault encrypt ansible/inventory/group_vars/vault.yml
ansible-playbook --check ansible/playbooks/deploy.yml
```

See [`ansible/README.md`](ansible/README.md) for the production sequence. The
playbook never runs a global Docker shutdown or cleanup command.

## OpenCode MCP

The repository includes a local FastMCP server under `mcp/`. Install it with:

```bash
make mcp-install
```

The project configuration at `.opencode/opencode.json` registers the MCP using
`stdio`. Export `NGC_KEY` before starting OpenCode, then restart OpenCode so it
loads the project MCP configuration:

```bash
export NGC_KEY='your-ngc-key'
opencode
```

Read-only TAO tools are enabled by default. Workspace mutations require
`TAO_MCP_ALLOW_MUTATIONS=true` and an explicit confirmation argument.

### MCP Tools

The MCP exposes these read-only tools to OpenCode:

- `tao_health`
- `tao_api_info`
- `tao_list_workspaces`
- `tao_get_workspace`
- `tao_list_datasets`
- `tao_list_jobs`
- `tao_get_job`
- `tao_get_job_logs`
- `tao_get_job_schema`
- `tao_list_base_experiments`
- `tao_list_gpu_types`

The following tools change TAO state and are disabled by default:

- `tao_create_workspace`
- `tao_delete_workspace`

Enable mutations only for a controlled session:

```bash
export TAO_MCP_ALLOW_MUTATIONS=true
```

Each mutation also requires `confirm="I_CONFIRM"`.

### MCP Authentication

The MCP authenticates against the TAO FTMS API using one of these options:

- `TAO_TOKEN`: an existing TAO JWT.
- `NGC_KEY` plus `TAO_ORG`: the MCP performs the TAO login and keeps the JWT in memory.

Do not put either credential in `.opencode/opencode.json`, Git, tool arguments,
or documentation. Export them only in the shell that starts OpenCode, or use a
local secret manager.

The MCP uses these non-secret defaults from `.opencode/opencode.json`:

```text
TAO_BASE_URL=http://100.107.81.126:8090
TAO_ORG=getter
TAO_MCP_ALLOW_MUTATIONS=false
```

### OpenCode Setup

The project file `.opencode/opencode.json` registers the MCP through `stdio`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "tao": {
      "type": "local",
      "command": [
        "mcp/.venv/bin/fastmcp",
        "run",
        "mcp/src/tao_mcp/server.py:mcp"
      ],
      "enabled": true
    }
  }
}
```

Install and verify the MCP:

```bash
make mcp-install
opencode mcp list
```

Expected output includes:

```text
tao connected
```

After changing `.opencode/opencode.json`, restart OpenCode. The running session
does not hot-reload MCP configuration.

### MCP Tests

Run the local MCP unit and protocol tests:

```bash
make mcp-test
```

The GitHub Actions workflow runs these tests on a public runner. Tests that
call the private FTMS endpoint run separately on a self-hosted runner with the
labels `self-hosted`, `linux`, and `tao-ftms`.

## License

This wrapper is Apache-2.0. NVIDIA TAO images, pretrained models, and their
licenses remain governed by NVIDIA and the respective NGC model cards.
