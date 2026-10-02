#!/usr/bin/env python3
"""Create an ephemeral OpenCode config for the prompt CI job."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    output = Path(os.environ["OPENCODE_CONFIG_OUTPUT"])
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": f"openai/{os.getenv('OPENAI_MODEL', 'gpt-5.6-luna')}",
        "provider": {
            "openai": {
                "options": {
                    "baseURL": os.environ["OPENAI_BASE_URL"],
                }
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
            }
        },
    }
    output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"config={output}")


if __name__ == "__main__":
    main()
