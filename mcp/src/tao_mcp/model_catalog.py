"""Small local catalog for trained TAO model versions."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any


_LOCK = RLock()


def catalog_path() -> Path:
    configured = os.getenv("TAO_MODEL_CATALOG_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".local" / "state" / "tao-mcp" / "models.json"


def _read() -> dict[str, Any]:
    path = catalog_path()
    if not path.exists():
        return {"models": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read model catalog {path}: {error}") from error
    if not isinstance(value, dict) or not isinstance(value.get("models", {}), dict):
        raise RuntimeError(f"Invalid model catalog format: {path}")
    return value


def _write(value: dict[str, Any]) -> None:
    path = catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=True, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _version_number(version: str) -> int | None:
    try:
        return int(version.removeprefix("v"))
    except ValueError:
        return None


def next_version(model_name: str) -> str:
    with _LOCK:
        versions = _read()["models"].get(model_name, {}).get("versions", [])
        numbers = [
            number
            for item in versions
            if (number := _version_number(str(item.get("version", "")))) is not None
        ]
        return f"v{max(numbers, default=0) + 1}"


def register(model: dict[str, Any]) -> dict[str, Any]:
    name = str(model["model_name"])
    version = str(model["version"])
    with _LOCK:
        catalog = _read()
        entry = catalog["models"].setdefault(name, {"model_name": name, "versions": []})
        versions = entry["versions"]
        if any(str(item.get("version")) == version for item in versions):
            raise ValueError(f"Model version already exists: {name} {version}")
        versions.append(model)
        versions.sort(key=lambda item: (_version_number(str(item.get("version", ""))) is None,
                                       _version_number(str(item.get("version", ""))) or 0,
                                       str(item.get("version", ""))))
        _write(catalog)
        return model


def list_models(model_name: str | None = None) -> list[dict[str, Any]]:
    with _LOCK:
        models = _read()["models"]
        if model_name:
            entry = models.get(model_name)
            return [entry] if entry else []
        return list(models.values())


def get_version(model_name: str, version: str) -> dict[str, Any]:
    with _LOCK:
        entry = _read()["models"].get(model_name)
        if not entry:
            raise KeyError(f"Model not found: {model_name}")
        for item in entry["versions"]:
            if str(item.get("version")) == version:
                return item
    raise KeyError(f"Model version not found: {model_name} {version}")
