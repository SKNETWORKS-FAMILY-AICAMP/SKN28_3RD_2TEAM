from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import SourceConfig


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a YAML mapping: {config_path}")
    if "sources" not in data or not isinstance(data["sources"], list):
        raise ValueError(f"Config must contain a sources list: {config_path}")
    return data


def load_sources(path: str | Path, only: set[str] | None = None) -> list[SourceConfig]:
    data = load_config(path)
    defaults = data.get("defaults", {})
    default_raw = defaults.get("raw", {}) if isinstance(defaults, dict) else {}
    default_processing = defaults.get("processing", {}) if isinstance(defaults, dict) else {}
    sources = []
    for item in data["sources"]:
        merged = dict(item)
        merged["raw"] = merge_dicts(default_raw, item.get("raw", {}))
        merged["processing"] = merge_dicts(default_processing, item.get("processing", {}))
        sources.append(SourceConfig.from_dict(merged))
    if only:
        sources = [source for source in sources if source.id in only]
    if not sources:
        raise ValueError("No sources selected")
    return sources


def merge_dicts(base: Any, override: Any) -> dict[str, Any]:
    result = dict(base) if isinstance(base, dict) else {}
    if not isinstance(override, dict):
        return result
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
