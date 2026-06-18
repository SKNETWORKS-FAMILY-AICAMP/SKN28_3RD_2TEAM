from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from .models import RawRecord
from .raw_manifest import RawManifestIndex


KST = timezone(timedelta(hours=9))


def now_kst() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def stable_id(*parts: str) -> str:
    joined = "|".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def safe_filename(value: str, fallback: str = "raw") -> str:
    value = unquote(value).strip().replace("\\", "/").split("/")[-1]
    value = re.sub(r"[^\w\uac00-\ud7a3.\-]+", "_", value, flags=re.UNICODE).strip("._")
    return value or fallback


def suffix_from_url(url: str, content_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix
    if suffix:
        return suffix
    if "html" in content_type:
        return ".html"
    if "json" in content_type:
        return ".json"
    if "javascript" in content_type:
        return ".js"
    if "pdf" in content_type:
        return ".pdf"
    return ".bin"


class RawStore:
    def __init__(self, output_root: str | Path) -> None:
        self.output_root = Path(output_root)
        self.raw_root = self.output_root / "raw"
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self._manifest_handles: dict[str, object] = {}
        self._skipped_handles: dict[str, object] = {}
        self._manifest_index = RawManifestIndex(self.raw_root)
        self.saved_count = 0
        self.reused_count = 0

    def close(self) -> None:
        for handle in self._manifest_handles.values():
            handle.close()
        for handle in self._skipped_handles.values():
            handle.close()
        self._manifest_handles.clear()
        self._skipped_handles.clear()

    def save(
        self,
        *,
        site: str,
        adapter: str,
        category: str,
        source_url: str,
        canonical_url: str,
        content: bytes,
        content_type: str,
        filename_hint: str | None = None,
        parent_source_id: str | None = None,
        metadata: dict | None = None,
    ) -> RawRecord:
        digest = sha256_bytes(content)
        source_id = f"{site}:{stable_id(category, canonical_url, digest[:16])}"
        suffix = suffix_from_url(canonical_url, content_type)
        filename_base = safe_filename(filename_hint or urlparse(canonical_url).path, category)
        if not Path(filename_base).suffix:
            filename_base += suffix
        filename = f"{Path(filename_base).stem}_{digest[:12]}{Path(filename_base).suffix}"
        relative_path = Path(site) / category / filename
        raw_path = self.raw_root / relative_path
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(content)

        record = RawRecord(
            source_id=source_id,
            site=site,
            adapter=adapter,
            source_url=source_url,
            canonical_url=canonical_url,
            content_type=content_type,
            raw_path=str(raw_path.as_posix()),
            sha256=digest,
            fetched_at=now_kst(),
            parent_source_id=parent_source_id,
            metadata=metadata or {},
        )
        self._append_manifest(site, record)
        self.saved_count += 1
        return record

    def find_existing(
        self,
        *,
        site: str,
        category: str,
        source_url: str,
    ) -> RawRecord | None:
        record = self._manifest_index.find(site=site, category=category, source_url=source_url)
        if record and Path(record.raw_path).exists():
            self.reused_count += 1
            return record
        return None

    def record_skipped_file(
        self,
        *,
        site: str,
        adapter: str,
        source_url: str,
        final_url: str | None,
        reason: str,
        metadata: dict | None = None,
    ) -> None:
        row = {
            "site": site,
            "adapter": adapter,
            "source_url": source_url,
            "final_url": final_url or "",
            "reason": reason,
            "fetched_at": now_kst(),
            "metadata": metadata or {},
        }
        if site not in self._skipped_handles:
            skipped_path = self.raw_root / site / "skipped_files.jsonl"
            skipped_path.parent.mkdir(parents=True, exist_ok=True)
            self._skipped_handles[site] = skipped_path.open("a", encoding="utf-8")
        handle = self._skipped_handles[site]
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()

    def _append_manifest(self, site: str, record: RawRecord) -> None:
        if site not in self._manifest_handles:
            manifest_path = self.raw_root / site / "manifest.jsonl"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            self._manifest_handles[site] = manifest_path.open("a", encoding="utf-8")
        handle = self._manifest_handles[site]
        handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        handle.flush()
