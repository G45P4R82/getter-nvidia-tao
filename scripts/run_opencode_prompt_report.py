#!/usr/bin/env python3
"""Run one real OpenCode prompt and capture a redacted experiment report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--report-dir", default="docs")
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"))
    parser.add_argument("--directory", default=".")
    return parser.parse_args()


def redact(value: str) -> str:
    value = re.sub(r"nvapi-[^\s\"']+", "[REDACTED_NGC_KEY]", value)
    value = re.sub(r"Bearer\s+[^\s\"']+", "Bearer [REDACTED_JWT]", value)
    return value


def event_summary(stdout: str) -> tuple[list[str], list[dict[str, object]]]:
    event_types: list[str] = []
    tools: list[dict[str, object]] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            if event.get("type"):
                event_types.append(str(event["type"]))
            part = event.get("part", {})
            tool = part.get("tool") if isinstance(part, dict) else None
            state = part.get("state", {}) if isinstance(part, dict) else {}
            if isinstance(tool, str):
                timing = state.get("time", {}) if isinstance(state, dict) else {}
                tools.append(
                    {
                        "tool": tool,
                        "status": str(state.get("status", "unknown")),
                        "call_id": str(part.get("callID", "")),
                        "input": state.get("input", {}),
                        "output": state.get("output"),
                        "error": state.get("error"),
                        "started": timing.get("start") if isinstance(timing, dict) else None,
                        "finished": timing.get("end") if isinstance(timing, dict) else None,
                    }
                )
    return sorted(set(event_types)), tools


def _walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def pipeline_is_final(tools: list[dict[str, object]]) -> bool:
    """Return true only after all pipeline actions reach a terminal state."""
    required = {"train", "evaluate", "export", "gen_trt_engine", "inference"}
    terminal = {"Done", "Completed", "Error", "Failed", "Failure", "Canceled", "Cancelled"}
    actions: dict[str, str] = {}
    for tool in tools:
        output = tool.get("output")
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                continue
        for item in _walk(output):
            action = item.get("action")
            job_id = item.get("id")
            status = item.get("status")
            if isinstance(action, str) and isinstance(job_id, str) and isinstance(status, str):
                actions[action] = status
    if any(status in {"Error", "Failed", "Failure", "Canceled", "Cancelled"} for status in actions.values()):
        return True
    return required.issubset(actions) and all(actions[action] in terminal for action in required)


def main() -> int:
    cli = args()
    artifact_dir = Path(cli.artifact_dir or Path(cli.report_dir) / f"experiment_{cli.experiment}")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prompt = Path(cli.prompt_file).read_text(encoding="utf-8")
    (artifact_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    command = [
        "opencode",
        "run",
        "--format",
        "json",
        "--auto",
        "--model",
        f"openai/{cli.model}",
        "--dir",
        cli.directory,
        prompt,
    ]
    started = dt.datetime.now(dt.timezone.utc)
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    finished = dt.datetime.now(dt.timezone.utc)
    stdout_parts = [process.stdout]
    stderr_parts = [process.stderr]
    event_types, tools = event_summary(process.stdout)
    session_id = ""
    for line in process.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = str(event.get("sessionID", ""))
        if session_id:
            break

    # A model turn can end while a real TAO job is still running. Continue the
    # same OpenCode session instead of publishing an intermediate report.
    continuation_count = 0
    while session_id and not pipeline_is_final(tools) and continuation_count < 15:
        continuation_count += 1
        continuation = [
            "Continue a mesma sessao do experimento 001. Nao finalize ainda. "
            "Consulte tao_get_job e tao_get_job_logs para todos os jobs ativos. "
            "Aguarde jobs Pending ou Started com novos polls. So avance para "
            "evaluate, export, gen_trt_engine e inference quando o job pai estiver "
            "terminal. So encerre depois que todas as cinco actions estiverem "
            "terminais ou uma action falhar definitivamente."
        ]
        next_process = subprocess.run(
            [
                "opencode",
                "run",
                "--format",
                "json",
                "--auto",
                "--model",
                f"openai/{cli.model}",
                "--dir",
                cli.directory,
                "--session",
                session_id,
                *continuation,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        stdout_parts.append(next_process.stdout)
        stderr_parts.append(next_process.stderr)
        _, next_tools = event_summary(next_process.stdout)
        tools.extend(next_tools)
        event_types.extend(item for item in event_summary(next_process.stdout)[0] if item not in event_types)
        if next_process.returncode != 0:
            process = next_process
            break
        time.sleep(1)
    stdout = redact("\n".join(stdout_parts))
    stderr = redact("\n".join(stderr_parts))
    event_types, tools = event_summary(stdout)
    (artifact_dir / "opencode-events.jsonl").write_text(stdout, encoding="utf-8")
    (artifact_dir / "opencode.stderr.log").write_text(stderr, encoding="utf-8")
    tool_names = sorted({item["tool"] for item in tools})
    (artifact_dir / "mcp-tool-calls.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=True, default=str) for item in tools) + "\n",
        encoding="utf-8",
    )
    tool_errors = [item for item in tools if item["status"] == "error"]
    if tool_errors or not pipeline_is_final(tools):
        process_returncode = 1
    else:
        process_returncode = process.returncode
    status = "PASSED" if process_returncode == 0 else "FAILED"
    report = [
        f"# Experiment {cli.experiment} - OpenCode Prompt",
        "",
        f"- Status: **{status}**",
        f"- Started (UTC): `{started.isoformat()}`",
        f"- Finished (UTC): `{finished.isoformat()}`",
        f"- Host: `{platform.node()}`",
        f"- Model: `openai/{cli.model}`",
        f"- TAO URL: `{os.getenv('TAO_BASE_URL', 'not set')}`",
        f"- OpenCode exit code: `{process.returncode}`",
        f"- MCP tool errors: `{len(tool_errors)}`",
        f"- OpenCode continuation turns: `{continuation_count}`",
        "",
        "## Prompt",
        "",
        "```text",
        redact(prompt).rstrip(),
        "```",
        "",
        "## MCP Observation",
        "",
        f"- Event types: `{', '.join(event_types) or 'none detected'}`",
        f"- MCP tool calls: `{len(tools)}`",
        f"- TAO/MCP tools detected: `{', '.join(tool_names) or 'none detected'}`",
        f"- Tool call manifest: `{artifact_dir / 'mcp-tool-calls.jsonl'}`",
        f"- Raw events: `{artifact_dir / 'opencode-events.jsonl'}`",
        "",
        "## Artifacts",
        "",
        f"- OpenCode stderr: `{artifact_dir / 'opencode.stderr.log'}`",
        "- TAO job logs, metrics, predictions and model artifacts are collected by the downstream TAO experiment runner.",
        "",
        "## Security",
        "",
        "Credentials and JWTs were redacted before writing this report.",
    ]
    report_path = Path(cli.report_dir) / f"experiment_{cli.experiment}-opencode.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"report={report_path}")
    return process_returncode


if __name__ == "__main__":
    sys.exit(main())
