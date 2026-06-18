from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kaist_crawler.models import RawRecord
from kaist_crawler.raw_manifest import RawManifestIndex, read_manifest_records


class RawManifestTests(unittest.TestCase):
    def test_index_finds_records_by_source_and_canonical_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp) / "raw"
            record = raw_record(raw_root)
            manifest_path = raw_root / "sample" / "manifest.jsonl"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False) + "\n", encoding="utf-8")

            index = RawManifestIndex(raw_root)

            by_source = index.find(site="sample", category="pages", source_url=record.source_url)
            by_canonical = index.find(site="sample", category="pages", source_url=record.canonical_url)
            self.assertEqual(by_source.source_id, record.source_id)
            self.assertEqual(by_canonical.source_id, record.source_id)

    def test_read_manifest_records_ignores_invalid_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_root = Path(tmp) / "raw"
            record = raw_record(raw_root)
            manifest_path = raw_root / "sample" / "manifest.jsonl"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                "{not-json}\n" + json.dumps(record.to_dict(), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            records = read_manifest_records(manifest_path)

            self.assertEqual([item.source_id for item in records], [record.source_id])


def raw_record(raw_root: Path) -> RawRecord:
    raw_path = raw_root / "sample" / "pages" / "index_abc.html"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("<html></html>", encoding="utf-8")
    return RawRecord(
        source_id="sample:abc",
        site="sample",
        adapter="static_html",
        source_url="https://example.edu/",
        canonical_url="https://example.edu/index.html",
        content_type="text/html",
        raw_path=str(raw_path),
        sha256="abc",
        fetched_at="2026-06-18T00:00:00+09:00",
    )


if __name__ == "__main__":
    unittest.main()
