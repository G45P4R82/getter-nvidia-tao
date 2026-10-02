"""Unit tests for the browsable experiment report builder."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_experiment_site import duration_seconds, job_rows, page


class ExperimentSiteTests(unittest.TestCase):
    def test_job_rows_extracts_nested_tao_jobs(self):
        tools = [
            {
                "tool": "tao_tao_submit_job",
                "output": {
                    "id": "12345678-1234-1234-1234-123456789012",
                    "action": "train",
                    "status": "Done",
                    "network_arch": "classification_pyt",
                },
            },
            {
                "tool": "tao_tao_get_job",
                "output": {
                    "job": {
                        "id": "12345678-1234-1234-1234-123456789012",
                        "status": "Done",
                    }
                },
            },
        ]
        jobs = job_rows(tools)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["action"], "train")

    def test_duration_uses_tao_timestamps(self):
        job = {
            "created_on": "2026-10-02T03:00:00+00:00",
            "last_modified": "2026-10-02T03:02:30+00:00",
        }
        self.assertEqual(duration_seconds(job), 150.0)

    def test_page_is_generated_without_inventing_missing_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report_root = root / "reports"
            artifact = report_root / "experiment_001-prompt-e2e"
            artifact.mkdir(parents=True)
            (report_root / "experiment_001-prompt-e2e-opencode.md").write_text(
                "# Report\n", encoding="utf-8"
            )
            (artifact / "mcp-tool-calls.jsonl").write_text(
                '{"tool":"tao_tao_health","status":"completed"}\n',
                encoding="utf-8",
            )
            (artifact / "opencode-events.jsonl").write_text("", encoding="utf-8")
            output = root / "site"
            page(report_root, output, "run-1", "experiment-001-prompt-1")
            content = (output / "reports/experiment-001-prompt-run-1/index.html").read_text(
                encoding="utf-8"
            )
            self.assertIn("Não fornecido pelo TAO", content)
            self.assertIn("CAPTURED", content)


if __name__ == "__main__":
    unittest.main()
