from __future__ import annotations

import json
from pathlib import Path

from .models import RawRecord


class RawManifestIndex:
    def __init__(self, raw_root: str | Path) -> None:
        self.raw_root = Path(raw_root)
        self._records_by_url = self._load_records()

    def find(self, *, site: str, category: str, source_url: str) -> RawRecord | None:
        return self._records_by_url.get((site, category, source_url))

    def _load_records(self) -> dict[tuple[str, str, str], RawRecord]:
        records: dict[tuple[str, str, str], RawRecord] = {}
        if not self.raw_root.exists():
            return records
        for manifest_path in self.raw_root.glob("*/manifest.jsonl"):
            site = manifest_path.parent.name
            for record in read_manifest_records(manifest_path):
                category = raw_record_category(record)
                records[(site, category, record.source_url)] = record
                records[(site, category, record.canonical_url)] = record
        return records


def read_manifest_records(manifest_path: Path) -> list[RawRecord]:
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records: list[RawRecord] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            records.append(RawRecord(**json.loads(line)))
        except (TypeError, json.JSONDecodeError):
            continue
    return records


def raw_record_category(record: RawRecord) -> str:
    return Path(record.raw_path).parent.name
