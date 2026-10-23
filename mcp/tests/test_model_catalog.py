from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tao_mcp.model_catalog import get_version, list_models, next_version, register
from tao_mcp import server


class ModelCatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "models.json"
        self.environment = patch.dict(
            os.environ,
            {"TAO_MODEL_CATALOG_PATH": str(self.path)},
            clear=False,
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_registers_and_lists_versions_in_order(self):
        first = {
            "model_name": "classification_pyt",
            "version": "v1",
            "job_id": "11111111-1111-1111-1111-111111111111",
            "artifact_uri": "seaweedfs://models/classification/v1",
        }
        second = {**first, "version": "v2", "job_id": "22222222-2222-2222-2222-222222222222"}
        register(second)
        register(first)

        models = list_models("classification_pyt")
        self.assertEqual([item["version"] for item in models[0]["versions"]], ["v1", "v2"])
        self.assertEqual(get_version("classification_pyt", "v2")["job_id"], second["job_id"])
        self.assertEqual(next_version("classification_pyt"), "v3")
        self.assertEqual(json.loads(self.path.read_text())["models"].keys(), {"classification_pyt"})

    def test_next_version_starts_at_v1(self):
        self.assertEqual(next_version("new-model"), "v1")

    def test_duplicate_version_is_rejected(self):
        model = {
            "model_name": "classification_pyt",
            "version": "v1",
            "job_id": "11111111-1111-1111-1111-111111111111",
        }
        register(model)
        with self.assertRaises(ValueError):
            register(model)

    def test_selected_version_becomes_parent_job(self):
        register(
            {
                "model_name": "classification_pyt",
                "version": "v1",
                "job_id": "11111111-1111-1111-1111-111111111111",
            }
        )
        with patch.dict(os.environ, {"TAO_MCP_ALLOW_MUTATIONS": "true"}), patch.object(
            server.client,
            "create_job",
            return_value={"id": "33333333-3333-3333-3333-333333333333"},
        ) as create_job:
            server.tao_submit_job.fn(
                network_arch="classification_pyt",
                action="inference",
                workspace_id="44444444-4444-4444-4444-444444444444",
                specs={},
                confirm="I_CONFIRM",
                model_name="classification_pyt",
                model_version="v1",
            )
        self.assertEqual(create_job.call_args.kwargs["parent_job_id"], "11111111-1111-1111-1111-111111111111")


if __name__ == "__main__":
    unittest.main()
