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

The default API endpoint is `http://localhost:8090`.

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

## License

This wrapper is Apache-2.0. NVIDIA TAO images, pretrained models, and their
licenses remain governed by NVIDIA and the respective NGC model cards.
