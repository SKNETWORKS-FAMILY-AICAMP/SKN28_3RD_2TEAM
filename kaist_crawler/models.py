from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceConfig:
    id: str
    name: str
    base_url: str
    adapter: str
    routes: list[str] = field(default_factory=list)
    known_files: list[str] = field(default_factory=list)
    dynamic_routes: dict[str, Any] = field(default_factory=dict)
    google_sheets: dict[str, Any] = field(default_factory=dict)
    raw_options: dict[str, Any] = field(default_factory=dict)
    processing_options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SourceConfig":
        return cls(
            id=raw["id"],
            name=raw["name"],
            base_url=raw["base_url"],
            adapter=raw["adapter"],
            routes=list(raw.get("routes", [])),
            known_files=list(raw.get("known_files", [])),
            dynamic_routes=dict(raw.get("dynamic_routes", {})),
            google_sheets=dict(raw.get("google_sheets", {})),
            raw_options=dict(raw.get("raw", {})),
            processing_options=dict(raw.get("processing", {})),
        )


@dataclass
class RawRecord:
    source_id: str
    site: str
    adapter: str
    source_url: str
    canonical_url: str
    content_type: str
    raw_path: str
    sha256: str
    fetched_at: str
    parent_source_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Document:
    doc_id: str
    site: str
    source_url: str
    title: str
    text: str
    raw_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    site: str
    source_url: str
    text: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
