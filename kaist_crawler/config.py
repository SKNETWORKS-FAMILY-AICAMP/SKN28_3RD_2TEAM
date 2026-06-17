from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import SourceConfig


SUPPORTED_ADAPTERS = {
    "static_html",
    "vite_react_spa",
    "vite_react_spa_with_google_sheets",
}

TOP_LEVEL_KEYS = {"version", "checked_at", "defaults", "sources"}
DEFAULT_KEYS = {
    "request_timeout_seconds",
    "polite_delay_seconds",
    "file_extensions",
    "raw_store",
    "processed_store",
    "vector_store",
    "raw",
    "processing",
}
SOURCE_KEYS = {
    "id",
    "name",
    "base_url",
    "adapter",
    "routes",
    "known_files",
    "dynamic_routes",
    "google_sheets",
    "raw",
    "processing",
    "robots_url",
    "sitemap_status",
    "route_aliases",
    "crawl_notes",
}


@dataclass(frozen=True)
class CrawlerConfig:
    sources: list[SourceConfig]
    request_timeout_seconds: int = 30
    polite_delay_seconds: float = 0.0


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a YAML mapping: {config_path}")
    if "sources" not in data or not isinstance(data["sources"], list):
        raise ValueError(f"Config must contain a sources list: {config_path}")
    validate_config(data, config_path)
    return data


def load_sources(path: str | Path, only: set[str] | None = None) -> list[SourceConfig]:
    return load_crawler_config(path, only).sources


def load_crawler_config(path: str | Path, only: set[str] | None = None) -> CrawlerConfig:
    data = load_config(path)
    return build_crawler_config(data, only=only, validate=False)


def build_crawler_config(
    data: dict[str, Any],
    only: set[str] | None = None,
    *,
    config_path: str | Path = "<memory>",
    validate: bool = True,
) -> CrawlerConfig:
    if validate:
        validate_config(data, Path(config_path))
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
        unknown = only - {source.id for source in sources}
        if unknown:
            raise ValueError(f"Unknown source id(s): {', '.join(sorted(unknown))}")
        sources = [source for source in sources if source.id in only]
    if not sources:
        raise ValueError("No sources selected")
    return CrawlerConfig(
        sources=sources,
        request_timeout_seconds=positive_int(
            defaults.get("request_timeout_seconds", 30),
            field_name="defaults.request_timeout_seconds",
        ),
        polite_delay_seconds=non_negative_float(
            defaults.get("polite_delay_seconds", 0.0),
            field_name="defaults.polite_delay_seconds",
        ),
    )


def validate_config(data: dict[str, Any], config_path: Path) -> None:
    unknown_top_level = set(data) - TOP_LEVEL_KEYS
    if unknown_top_level:
        raise ValueError(f"Unknown top-level config key(s) in {config_path}: {', '.join(sorted(unknown_top_level))}")

    defaults = data.get("defaults", {})
    if defaults and not isinstance(defaults, dict):
        raise ValueError("Config defaults must be a mapping")
    unknown_defaults = set(defaults) - DEFAULT_KEYS if isinstance(defaults, dict) else set()
    if unknown_defaults:
        raise ValueError(f"Unknown defaults key(s): {', '.join(sorted(unknown_defaults))}")
    if isinstance(defaults, dict):
        positive_int(defaults.get("request_timeout_seconds", 30), field_name="defaults.request_timeout_seconds")
        non_negative_float(defaults.get("polite_delay_seconds", 0.0), field_name="defaults.polite_delay_seconds")

    seen_ids: set[str] = set()
    for index, source in enumerate(data["sources"], start=1):
        validate_source_config(source, index=index, seen_ids=seen_ids)


def validate_source_config(source: Any, *, index: int, seen_ids: set[str]) -> None:
    if not isinstance(source, dict):
        raise ValueError(f"sources[{index}] must be a mapping")

    unknown_keys = set(source) - SOURCE_KEYS
    if unknown_keys:
        raise ValueError(f"Unknown key(s) in sources[{index}]: {', '.join(sorted(unknown_keys))}")

    for key in ("id", "name", "base_url", "adapter"):
        value = source.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"sources[{index}].{key} must be a non-empty string")

    source_id = source["id"]
    if source_id in seen_ids:
        raise ValueError(f"Duplicate source id: {source_id}")
    seen_ids.add(source_id)

    adapter = source["adapter"]
    if adapter not in SUPPORTED_ADAPTERS:
        raise ValueError(f"Unsupported adapter for {source_id}: {adapter}")

    for key in ("routes", "known_files", "crawl_notes"):
        if key in source and not isinstance(source[key], list):
            raise ValueError(f"{source_id}.{key} must be a list")

    for key in ("dynamic_routes", "google_sheets", "raw", "processing", "route_aliases"):
        if key in source and not isinstance(source[key], dict):
            raise ValueError(f"{source_id}.{key} must be a mapping")


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


def positive_int(value: Any, *, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return parsed


def non_negative_float(value: Any, *, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a non-negative number") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative number")
    return parsed
