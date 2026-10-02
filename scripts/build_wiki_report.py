#!/usr/bin/env python3
"""Build one technical Markdown page and SVG charts for the GitHub Wiki."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import shutil
from pathlib import Path

from build_experiment_site import duration_seconds, fmt_seconds, job_rows, load_json_lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", required=True)
    parser.add_argument("--wiki-root", required=True)
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def chart(path: Path, title: str, values: list[tuple[str, float]], color: str) -> None:
    width, height = 900, 320
    maximum = max((value for _, value in values), default=1.0) or 1.0
    slot = (width - 100) / max(1, len(values))
    bars = []
    for index, (label, value) in enumerate(values):
        x = 60 + index * slot
        bar_height = 190 * value / maximum
        y = 245 - bar_height
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{min(56, slot - 12):.1f}" height="{bar_height:.1f}" fill="{color}" rx="5"/>'
            f'<text x="{x + min(56, slot - 12) / 2:.1f}" y="265" text-anchor="middle">{esc(label[:14])}</text>'
            f'<text x="{x + min(56, slot - 12) / 2:.1f}" y="{max(18, y - 8):.1f}" text-anchor="middle">{value:.1f}</text>'
        )
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="#172333" rx="12"/>'
        f'<text x="30" y="35" fill="#e8eef5" font-family="sans-serif" font-size="20">{esc(title)}</text>'
        f'<line x1="40" y1="245" x2="870" y2="245" stroke="#9fb0c2"/>'
        f'<g fill="#b9c7d5" font-family="sans-serif" font-size="13">{"".join(bars)}</g></svg>',
        encoding="utf-8",
    )


def main() -> None:
    cli = parse_args()
    report_root = Path(cli.report_root)
    wiki = Path(cli.wiki_root)
    report = next(report_root.glob("**/*prompt-e2e-opencode.md"), None)
    artifact = next(report_root.glob("**/experiment_001-prompt-e2e"), report_root)
    tools = load_json_lines(artifact / "mcp-tool-calls.jsonl")
    jobs = job_rows(tools)
    slug = f"Experiment-001-Prompt-{cli.run_id}"
    raw = wiki / "assets" / slug
    raw.mkdir(parents=True, exist_ok=True)
    for source in artifact.glob("*"):
        if source.is_file():
            shutil.copy2(source, raw / source.name)
    durations = [(str(job.get("action", "job")), duration_seconds(job) or 0.0) for job in jobs]
    chart(raw / "job-duration.svg", "Duração dos jobs TAO (segundos)", durations, "#159a72")
    counts: dict[str, int] = {}
    for tool in tools:
        name = str(tool.get("tool", "unknown"))
        counts[name] = counts.get(name, 0) + 1
    chart(raw / "mcp-tools.svg", "Chamadas MCP por ferramenta", [(k, float(v)) for k, v in counts.items()], "#7b61ff")
    failed = [job for job in jobs if str(job.get("status", "")) in {"Error", "Failed", "Failure", "Canceled", "Cancelled"}]
    actions = {str(job.get("action", "")) for job in jobs}
    required_actions = {"train", "evaluate", "export", "gen_trt_engine", "inference"}
    unfinished = [job for job in jobs if str(job.get("status", "")) not in {"Done", "Completed"}]
    status = "FAILED" if failed else (
        "INCOMPLETE" if not jobs or unfinished or not required_actions.issubset(actions) else "PASSED"
    )
    table = "\n".join(
        f"| `{job.get('action', 'unknown')}` | `{job.get('id')}` | **{job.get('status', 'unknown')}** | {fmt_seconds(duration_seconds(job))} | {job.get('network_arch', 'Não disponível')} |"
        for job in jobs
    ) or "| - | - | Nenhum job identificado | - | - |"
    calls = "\n".join(
        f"| {index} | `{call.get('tool')}` | {call.get('status')} | `{call.get('call_id')}` |"
        for index, call in enumerate(tools, 1)
    ) or "| - | - | - | - |"
    original = report.read_text(encoding="utf-8") if report else "Relatório original ausente."
    page = f'''# Experiment 001 - Prompt E2E - {cli.run_id}

> Relatório técnico gerado a partir das chamadas reais OpenCode -> TAO MCP -> TAO FTMS.

## Resumo

| Campo | Resultado |
| --- | --- |
| Status da orquestração | Capturado |
| Status do pipeline TAO | **{status}** |
| Jobs identificados | {len(jobs)} |
| Chamadas MCP | {len(tools)} |
| Erros MCP | {sum(call.get("status") == "error" for call in tools)} |
| Tempo observado | {fmt_seconds(sum(value for _, value in durations))} |
| Data de geração | {dt.datetime.now(dt.timezone.utc).isoformat()} |

## Duração do pipeline

![Duração dos jobs TAO](assets/{slug}/job-duration.svg)

## Chamadas MCP

![Chamadas MCP](assets/{slug}/mcp-tools.svg)

| # | Ferramenta | Status | Call ID |
| ---: | --- | --- | --- |
{calls}

## Jobs NVIDIA TAO

| Ação | Job ID | Status | Duração | Arquitetura |
| --- | --- | --- | --- | --- |
{table}

## Dataset e configuração

Os URIs, workspace, dataset, modelo base e especificações retornados pelo TAO estão em `assets/{slug}/mcp-tool-calls.jsonl`.

Links `seaweedfs://` são identificadores internos do armazenamento TAO e não são convertidos em links HTTP inexistentes. Métricas não fornecidas pela API são marcadas como **não fornecidas**, nunca como zero.

## Métricas e evidências

As métricas de época, avaliação, throughput, latência, tamanho do dataset e artefatos aparecem quando retornadas pelo TAO nos outputs e logs capturados. A ausência de um campo não autoriza inferência numérica.

## Análise crítica e trade-offs

- O tempo de GPU deve ser comparado à métrica final e à qualidade do conjunto de avaliação, não apenas ao término do job.
- Um mesmo dataset em treino e avaliação reduz a força da conclusão sobre generalização; uma divisão independente precisa ser confirmada.
- Exportação ONNX e geração TensorRT bem-sucedidas não provam equivalência numérica. Isso exige comparação das predições e métricas em cada formato.
- TensorRT pode reduzir latência e aumentar throughput, mas batch size, precisão e hardware precisam ser mantidos explícitos para uma comparação válida.
- Quando latência, throughput ou custo não aparecem nos dados do TAO, a conclusão correta é **não determinado nesta execução**.

## Dados brutos

- [Chamadas MCP estruturadas](assets/{slug}/mcp-tool-calls.jsonl)
- [Eventos OpenCode](assets/{slug}/opencode-events.jsonl)
- [Prompt](assets/{slug}/prompt.txt)
- [Relatório original](assets/{slug}/report.md)

<details><summary>Relatório Markdown original</summary>

```text
{html.escape(original)}
```
</details>
'''
    (raw / "report.md").write_text(original, encoding="utf-8")
    (wiki / f"{slug}.md").write_text(page, encoding="utf-8")
    entries = sorted(wiki.glob("Experiment-001-Prompt-*.md"), reverse=True)
    index = "# Getter NVIDIA TAO - Relatórios\n\nRelatórios técnicos de execuções reais.\n\n"
    index += "\n".join(f"- [{path.stem}]({path.name})" for path in entries) + "\n"
    (wiki / "Home.md").write_text(index, encoding="utf-8")


if __name__ == "__main__":
    main()
