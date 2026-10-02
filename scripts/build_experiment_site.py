#!/usr/bin/env python3
"""Build a browsable, dependency-free HTML report for a TAO run."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import html
import json
import shutil
from pathlib import Path
from urllib.parse import quote


TERMINAL_FAILURES = {"Error", "Failed", "Failure", "Canceled", "Cancelled"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--release-tag", default="")
    parser.add_argument("--previous-site", default="")
    return parser.parse_args()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load_json_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def json_value(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def job_rows(tools: list[dict]) -> list[dict]:
    jobs: dict[str, dict] = {}
    for call in tools:
        for item in walk(json_value(call.get("output"))):
            job_id = item.get("id")
            if not isinstance(job_id, str) or len(job_id) < 8:
                continue
            if not any(key in item for key in ("action", "job_details", "network_arch")):
                continue
            row = jobs.setdefault(job_id, {"id": job_id})
            row.update({key: value for key, value in item.items() if key not in {"id"} or key not in row})
            if call.get("tool") == "tao_tao_submit_job":
                row.setdefault("submitted_by", call.get("tool"))
    return list(jobs.values())


def duration_seconds(job: dict) -> float | None:
    try:
        start = dt.datetime.fromisoformat(str(job["created_on"]).replace("Z", "+00:00"))
        end = dt.datetime.fromisoformat(str(job["last_modified"]).replace("Z", "+00:00"))
        return max(0.0, (end - start).total_seconds())
    except (KeyError, TypeError, ValueError):
        return None


def fmt_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "Não disponível"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f} min"


def bar_chart(title: str, values: list[tuple[str, float]], color: str = "#1d75bd") -> str:
    width, height = 760, 250
    max_value = max((value for _, value in values), default=1.0) or 1.0
    bars = []
    for index, (label, value) in enumerate(values):
        x = 30 + index * max(50, (width - 50) / max(1, len(values)))
        bar_height = 150 * value / max_value
        y = 190 - bar_height
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="34" height="{bar_height:.1f}" rx="4" fill="{color}"/>'
            f'<text x="{x + 17:.1f}" y="210" text-anchor="middle">{esc(label[:12])}</text>'
            f'<text x="{x + 17:.1f}" y="{max(15, y - 6):.1f}" text-anchor="middle">{value:.1f}</text>'
        )
    return f'<div class="chart"><h3>{esc(title)}</h3><svg viewBox="0 0 {width} {height}" role="img">{"".join(bars)}</svg></div>'


def page(report_root: Path, output: Path, run_id: str, release_tag: str) -> None:
    report = next(report_root.glob("**/*prompt-e2e-opencode.md"), None)
    artifact_dir = next(report_root.glob("**/experiment_001-prompt-e2e"), report_root)
    tools = load_json_lines(artifact_dir / "mcp-tool-calls.jsonl")
    jobs = job_rows(tools)
    report_text = report.read_text(encoding="utf-8") if report else "Relatório não encontrado."
    failed_jobs = [job for job in jobs if str(job.get("status", "")) in TERMINAL_FAILURES]
    actions = {str(job.get("action", "")) for job in jobs}
    required_actions = {"train", "evaluate", "export", "gen_trt_engine", "inference"}
    unfinished = [job for job in jobs if str(job.get("status", "")) not in {"Done", "Completed"}]
    pipeline_status = "FAILED" if failed_jobs else (
        "INCOMPLETE" if not jobs or unfinished or not required_actions.issubset(actions) else "PASSED"
    )
    run_slug = f"experiment-001-prompt-{run_id}"
    target = output / "reports" / run_slug
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(artifact_dir, target / "raw", dirs_exist_ok=True)
    durations = [(str(job.get("action", "job")), duration_seconds(job) or 0) for job in jobs]
    total = sum(value for _, value in durations)
    tool_counts: dict[str, int] = {}
    for tool in tools:
        name = str(tool.get("tool", "unknown"))
        tool_counts[name] = tool_counts.get(name, 0) + 1
    tool_chart = bar_chart("Chamadas MCP por ferramenta", list(tool_counts.items()), "#7b61ff")
    duration_chart = bar_chart("Duração dos jobs TAO", durations, "#159a72")
    job_table = "".join(
        "<tr>"
        f"<td><code>{esc(job.get('action', 'unknown'))}</code></td>"
        f"<td><code>{esc(job.get('id'))}</code></td>"
        f"<td><strong class=\"status-{esc(str(job.get('status', 'unknown')).lower())}\">{esc(job.get('status', 'unknown'))}</strong></td>"
        f"<td>{fmt_seconds(duration_seconds(job))}</td>"
        f"<td>{esc(job.get('network_arch', 'Não disponível'))}</td>"
        "</tr>"
        for job in jobs
    ) or '<tr><td colspan="5">Nenhum job TAO foi identificado nos dados capturados.</td></tr>'
    call_table = "".join(
        "<tr>"
        f"<td>{index}</td><td><code>{esc(call.get('tool'))}</code></td>"
        f"<td>{esc(call.get('status'))}</td><td>{esc(call.get('call_id'))}</td>"
        "</tr>"
        for index, call in enumerate(tools, 1)
    )
    release_link = f'<a href="https://github.com/G45P4R82/getter-nvidia-tao/releases/tag/{quote(release_tag)}">Release bruto</a>' if release_tag else "Release bruto não informado"
    html_page = f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(run_slug)}</title><style>
:root{{color-scheme:dark;--bg:#0e1621;--panel:#172333;--text:#e8eef5;--muted:#9fb0c2;--accent:#51b5e8;--danger:#ff7777;--ok:#62d49c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:36px 20px}}h1{{font-size:34px;margin-bottom:4px}}h2{{margin-top:38px;border-bottom:1px solid #2c4054;padding-bottom:8px}}h3{{font-size:16px;color:var(--muted)}}.lede{{color:var(--muted);font-size:17px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}}.card,.chart{{background:var(--panel);border:1px solid #293d51;border-radius:12px;padding:16px}}.value{{font-size:27px;font-weight:700}}.label{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}}.ok{{color:var(--ok)}}.bad,.status-error,.status-failed{{color:var(--danger)}}table{{width:100%;border-collapse:collapse;background:var(--panel);border-radius:10px;overflow:hidden}}th,td{{padding:11px;text-align:left;border-bottom:1px solid #293d51;vertical-align:top}}th{{color:var(--muted);font-size:12px;text-transform:uppercase}}code,pre{{font-family:ui-monospace,monospace}}code{{color:#a9d8f1}}pre{{white-space:pre-wrap;background:#0a1018;padding:16px;border-radius:8px;max-height:500px;overflow:auto}}a{{color:var(--accent)}}svg{{width:100%;height:auto}}svg text{{fill:#b9c7d5;font:12px system-ui}}.note{{border-left:3px solid var(--accent);padding:10px 14px;background:#122435;color:var(--muted)}}@media(max-width:650px){{h1{{font-size:25px}}th,td{{font-size:12px;padding:8px}}}}
</style></head><body><main>
<p><a href="../../index.html">← Todas as execuções</a></p><h1>Experiment 001 · Prompt E2E</h1>
<p class="lede">Relatório técnico da execução <code>{esc(run_id)}</code>, gerado a partir das observações do OpenCode e do TAO MCP.</p>
<div class="grid"><div class="card"><div class="label">Orquestração OpenCode</div><div class="value ok">CAPTURED</div></div><div class="card"><div class="label">Pipeline TAO</div><div class="value {'bad' if pipeline_status == 'FAILED' else 'ok'}">{pipeline_status}</div></div><div class="card"><div class="label">Jobs identificados</div><div class="value">{len(jobs)}</div></div><div class="card"><div class="label">Tempo observado</div><div class="value">{fmt_seconds(total)}</div></div><div class="card"><div class="label">Erros MCP</div><div class="value {'bad' if any(c.get('status') == 'error' for c in tools) else 'ok'}">{sum(c.get('status') == 'error' for c in tools)}</div></div></div>
<h2>Resumo executivo</h2><div class="note">O status de orquestração não é tratado como prova de sucesso do treinamento. As conclusões abaixo usam apenas jobs, métricas e respostas efetivamente capturados. Dados ausentes são marcados como não disponíveis.</div>
<h2>Tempo e pipeline</h2><div class="grid">{duration_chart}{tool_chart}</div>
<h2>Jobs NVIDIA TAO</h2><table><thead><tr><th>Ação</th><th>ID</th><th>Status</th><th>Duração</th><th>Arquitetura</th></tr></thead><tbody>{job_table}</tbody></table>
<h2>Chamadas MCP observadas</h2><table><thead><tr><th>#</th><th>Ferramenta</th><th>Status</th><th>Call ID</th></tr></thead><tbody>{call_table}</tbody></table>
<h2>Dataset e configuração</h2><p>Os URIs e metadados retornados pelo TAO estão preservados nos dados brutos desta página. Links públicos para <code>seaweedfs://</code> não são fabricados: o armazenamento não é um endereço HTTP navegável.</p><p><a href="raw/mcp-tool-calls.jsonl">Abrir chamadas MCP estruturadas</a> · <a href="raw/opencode-events.jsonl">Abrir eventos OpenCode</a> · {release_link}</p>
<h2>Métricas e evidências</h2><p>Métricas de época, avaliação, throughput, latência, tamanho do dataset e artefatos aparecem aqui quando fornecidas pela API/logs do TAO. Nesta rodada, a ausência de um campo significa <strong>Não fornecido pelo TAO nesta execução</strong>, não zero.</p>
<h2>Análise crítica e trade-offs</h2><ul><li>Tempo de GPU deve ser comparado com a métrica final, não apenas com o término do job.</li><li>Inferência e TensorRT só podem ser comparados quantitativamente quando latência e throughput forem retornados pelo TAO.</li><li>Um resultado de avaliação não prova generalização se treino e avaliação usam o mesmo conjunto sem uma divisão independente documentada.</li><li>Exportação bem-sucedida não prova equivalência numérica; isso exige comparação de predições e métricas entre formatos.</li></ul>
<h2>Relatório bruto</h2><details><summary>Mostrar Markdown original</summary><pre>{esc(report_text)}</pre></details>
</main></body></html>'''
    (target / "index.html").write_text(html_page, encoding="utf-8")
    build_index(output)


def build_index(output: Path) -> None:
    rows = []
    for index in sorted((output / "reports").glob("*/index.html")):
        slug = index.parent.name
        rows.append(f'<tr><td><a href="reports/{esc(slug)}/">{esc(slug)}</a></td><td>Relatório técnico</td></tr>')
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Getter NVIDIA TAO · Relatórios</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 20px;background:#0e1621;color:#e8eef5}a{color:#51b5e8}table{width:100%;border-collapse:collapse}td{padding:14px;border-bottom:1px solid #293d51}</style>'
        '<h1>Getter NVIDIA TAO</h1><p>Relatórios técnicos de execuções reais OpenCode → MCP → TAO.</p><table><tr><th>Execução</th><th>Tipo</th></tr>'
        + "".join(rows) + '</table>', encoding="utf-8"
    )


def main() -> None:
    cli = parse_args()
    output = Path(cli.output)
    if cli.previous_site and Path(cli.previous_site).exists():
        shutil.copytree(cli.previous_site, output, dirs_exist_ok=True)
    page(Path(cli.report_root), output, cli.run_id, cli.release_tag)


if __name__ == "__main__":
    main()
