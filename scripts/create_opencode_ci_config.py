#!/usr/bin/env python3
"""Create an ephemeral OpenCode config for the prompt CI job."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    output = Path(os.environ["OPENCODE_CONFIG_OUTPUT"])
    provider_options = {"baseURL": os.environ["OPENAI_BASE_URL"]}
    if os.getenv("OPENAI_AUTH_MODE", "api_key") != "azure_ad":
        provider_options["headers"] = {"api-key": os.environ["OPENAI_API_KEY"]}
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": f"openai/{os.getenv('OPENAI_MODEL', 'gpt-4.1')}",
        "provider": {
            "openai": {
                "options": provider_options
            }
        },
        "mcp": {
            "tao": {
                "type": "local",
                "command": [
                    "mcp/.venv/bin/fastmcp",
                    "run",
                    "mcp/src/tao_mcp/server.py:mcp",
                ],
                "enabled": True,
                "timeout": 30000,
                "environment": {
                    "TAO_BASE_URL": os.environ.get("TAO_BASE_URL", ""),
                    "TAO_ORG": os.environ.get("TAO_ORG", "getter"),
                    "TAO_MCP_ALLOW_MUTATIONS": os.environ.get(
                        "TAO_MCP_ALLOW_MUTATIONS", "false"
                    ),
                    "TAO_TEST_WORKSPACE_ID": os.environ.get("TAO_TEST_WORKSPACE_ID", ""),
                    "TAO_TRAIN_DATASET_URI": os.environ.get("TAO_TRAIN_DATASET_URI", ""),
                    "TAO_EVAL_DATASET_URI": os.environ.get("TAO_EVAL_DATASET_URI", ""),
                    "TAO_INFERENCE_DATASET_URI": os.environ.get(
                        "TAO_INFERENCE_DATASET_URI", ""
                    ),
                    "TAO_BASE_EXPERIMENT_IDS": os.environ.get(
                        "TAO_BASE_EXPERIMENT_IDS", ""
                    ),
                    "TAO_REAL_NETWORK": os.environ.get(
                        "TAO_REAL_NETWORK", "classification_pyt"
                    ),
                },
            }
        },
    }
    output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"config={output}")


if __name__ == "__main__":
    main()
