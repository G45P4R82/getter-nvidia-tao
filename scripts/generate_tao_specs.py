#!/usr/bin/env python3
"""Generate real TAO action specs from the authenticated FTMS schemas."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = os.getenv("TAO_BASE_URL", "http://localhost:8090").rstrip("/")
    org = os.getenv("TAO_ORG", "getter")
    token = os.getenv("TAO_TOKEN", "")
    key = os.getenv("NGC_KEY", "")
    client = httpx.Client(base_url=base, timeout=120)
    try:
        if not token and key:
            response = client.post(
                "/api/v2/login",
                headers={"ngc_key": key},
                json={"ngc_key": key, "ngc_org_name": org, "enable_telemetry": False},
            )
            response.raise_for_status()
            token = response.json()["token"]
        if not token:
            raise RuntimeError("TAO_TOKEN or NGC_KEY is required")
        headers = {"Authorization": f"Bearer {token}"}
        network = os.getenv("TAO_REAL_NETWORK", "classification_pyt")
        dataset = os.getenv("TAO_TRAIN_DATASET_URI", "")
        if not dataset:
            raise RuntimeError("TAO_TRAIN_DATASET_URI is required")
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        for action in ("train", "evaluate", "export", "gen_trt_engine", "inference"):
            response = client.get(
                f"/api/v2/orgs/{org}/jobs:schema",
                headers=headers,
                params={"network_arch": network, "action": action},
            )
            response.raise_for_status()
            schema = response.json()
            spec = copy.deepcopy(schema.get("default", schema))
            if not isinstance(spec, dict):
                raise RuntimeError(f"TAO schema for {action} did not return an object default")
            dataset_spec = spec.setdefault("dataset", {})
            if isinstance(dataset_spec, dict):
                dataset_spec["num_classes"] = int(os.getenv("TAO_NUM_CLASSES", "2"))
                if action in {"export", "gen_trt_engine", "inference"}:
                    dataset_spec["classes_file"] = f"{dataset.rstrip('/')}/classes.txt"
                if action in {"gen_trt_engine", "inference"}:
                    dataset_spec["batch_size"] = 1
            train_spec = spec.setdefault("train", {})
            if action == "train" and isinstance(train_spec, dict):
                train_spec["num_epochs"] = 1
                train_spec["num_gpus"] = 1
            if action == "inference" and isinstance(spec.get("inference"), dict):
                spec["inference"]["batch_size"] = 1
            (output / f"{action}.json").write_text(
                json.dumps(spec, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
            )
            print(f"generated={action}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
