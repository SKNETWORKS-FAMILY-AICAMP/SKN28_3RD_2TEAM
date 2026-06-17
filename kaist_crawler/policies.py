from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Chunk, Document, RawRecord


@dataclass(frozen=True)
class PolicyDecision:
    skip: bool
    reason: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class FilePolicy:
    max_file_size_mb: float | None = None
    exclude_url_patterns: tuple[str, ...] = ()
    include_url_patterns: tuple[str, ...] = ()
    skip_unknown_size: bool = False

    @classmethod
    def from_options(cls, options: dict[str, Any] | None) -> "FilePolicy":
        options = options or {}
        max_file_size_mb = options.get("max_file_size_mb")
        if max_file_size_mb is not None:
            max_file_size_mb = float(max_file_size_mb)
        return cls(
            max_file_size_mb=max_file_size_mb,
            exclude_url_patterns=tuple(options.get("exclude_url_patterns", [])),
            include_url_patterns=tuple(options.get("include_url_patterns", [])),
            skip_unknown_size=bool(options.get("skip_unknown_size", False)),
        )

    def evaluate(
        self,
        *,
        requested_url: str,
        final_url: str | None = None,
        content_length: int | None = None,
        content_type: str = "",
    ) -> PolicyDecision:
        target = " ".join(part for part in [requested_url, final_url or "", content_type] if part)
        include_matched = pattern_matches_any(target, self.include_url_patterns)
        exclude_pattern = matching_pattern(target, self.exclude_url_patterns)
        if exclude_pattern and not include_matched:
            return PolicyDecision(
                skip=True,
                reason="excluded_url_pattern",
                metadata={"pattern": exclude_pattern},
            )
        if self.include_url_patterns and not include_matched:
            return PolicyDecision(skip=True, reason="not_included_by_file_policy")
        if self.max_file_size_mb is not None:
            max_bytes = int(self.max_file_size_mb * 1024 * 1024)
            if content_length is None:
                if self.skip_unknown_size:
                    return PolicyDecision(skip=True, reason="unknown_file_size")
            elif content_length > max_bytes and not include_matched:
                return PolicyDecision(
                    skip=True,
                    reason="file_too_large",
                    metadata={
                        "content_length": content_length,
                        "max_file_size_mb": self.max_file_size_mb,
                    },
                )
        return PolicyDecision(skip=False)


@dataclass(frozen=True)
class ProcessingFilterPolicy:
    skip_duplicate_raw_sha: bool = True
    skip_duplicate_document_text: bool = True
    skip_duplicate_chunks: bool = True
    min_text_chars: int = 200
    min_text_chars_by_type: dict[str, int] | None = None
    exclude_document_types: tuple[str, ...] = ()
    max_pdf_size_mb: float | None = None
    exclude_pdf_url_patterns: tuple[str, ...] = ()
    exclude_asset_url_patterns: tuple[str, ...] = ()
    include_html_url_patterns: tuple[str, ...] = ()
    exclude_html_url_patterns: tuple[str, ...] = ()

    @classmethod
    def from_options(cls, options: dict[str, Any] | None) -> "ProcessingFilterPolicy":
        options = options or {}
        max_pdf_size_mb = options.get("max_pdf_size_mb")
        if max_pdf_size_mb is not None:
            max_pdf_size_mb = float(max_pdf_size_mb)
        return cls(
            skip_duplicate_raw_sha=bool(options.get("skip_duplicate_raw_sha", True)),
            skip_duplicate_document_text=bool(options.get("skip_duplicate_document_text", True)),
            skip_duplicate_chunks=bool(options.get("skip_duplicate_chunks", True)),
            min_text_chars=int(options.get("min_text_chars", 200)),
            min_text_chars_by_type=dict(options.get("min_text_chars_by_type", {})),
            exclude_document_types=tuple(options.get("exclude_document_types", [])),
            max_pdf_size_mb=max_pdf_size_mb,
            exclude_pdf_url_patterns=tuple(options.get("exclude_pdf_url_patterns", [])),
            exclude_asset_url_patterns=tuple(options.get("exclude_asset_url_patterns", [])),
            include_html_url_patterns=tuple(options.get("include_html_url_patterns", [])),
            exclude_html_url_patterns=tuple(options.get("exclude_html_url_patterns", [])),
        )

    def evaluate_raw_record(
        self,
        *,
        record: RawRecord,
        raw_path: Path,
        category: str,
        seen_sha: set[str],
    ) -> PolicyDecision:
        if self.skip_duplicate_raw_sha and record.sha256 in seen_sha:
            return PolicyDecision(skip=True, reason="duplicate_raw_sha", metadata={"sha256": record.sha256})

        target = " ".join([record.source_url, record.canonical_url, str(raw_path)])
        suffix = raw_path.suffix.lower()
        if category == "assets" and suffix == ".js":
            pattern = matching_pattern(target, self.exclude_asset_url_patterns)
            if pattern:
                return PolicyDecision(skip=True, reason="excluded_asset_pattern", metadata={"pattern": pattern})

        if category == "files" and suffix == ".pdf":
            pattern = matching_pattern(target, self.exclude_pdf_url_patterns)
            if pattern:
                return PolicyDecision(skip=True, reason="excluded_pdf_pattern", metadata={"pattern": pattern})
            if self.max_pdf_size_mb is not None and raw_path.exists():
                size = raw_path.stat().st_size
                max_bytes = int(self.max_pdf_size_mb * 1024 * 1024)
                if size > max_bytes:
                    return PolicyDecision(
                        skip=True,
                        reason="pdf_too_large",
                        metadata={"size": size, "max_pdf_size_mb": self.max_pdf_size_mb},
                    )
        return PolicyDecision(skip=False)

    def evaluate_document(self, *, document: Document, seen_text_hashes: set[str]) -> PolicyDecision:
        document_type = str(document.metadata.get("document_type", ""))
        if document_type in self.exclude_document_types:
            return PolicyDecision(skip=True, reason="excluded_document_type", metadata={"document_type": document_type})

        if document_type in {"html", "rendered_html", "html_shell"}:
            target = " ".join([document.source_url, document.raw_path or ""])
            include_matched = pattern_matches_any(target, self.include_html_url_patterns)
            if self.include_html_url_patterns and not include_matched:
                return PolicyDecision(skip=True, reason="html_not_included_by_policy")
            pattern = matching_pattern(target, self.exclude_html_url_patterns)
            if pattern:
                return PolicyDecision(skip=True, reason="excluded_html_pattern", metadata={"pattern": pattern})

        min_chars = self.min_text_chars
        if self.min_text_chars_by_type and document_type in self.min_text_chars_by_type:
            min_chars = int(self.min_text_chars_by_type[document_type])
        if len(document.text.strip()) < min_chars:
            return PolicyDecision(
                skip=True,
                reason="document_too_short",
                metadata={"document_type": document_type, "min_text_chars": min_chars},
            )

        text_hash = normalized_text_hash(document.text)
        if self.skip_duplicate_document_text and text_hash in seen_text_hashes:
            return PolicyDecision(skip=True, reason="duplicate_document_text", metadata={"text_hash": text_hash})
        return PolicyDecision(skip=False, metadata={"text_hash": text_hash})


def filter_documents(
    documents: list[Document],
    policy_by_site: dict[str, ProcessingFilterPolicy],
) -> tuple[list[Document], list[dict]]:
    kept: list[Document] = []
    filtered: list[dict] = []
    seen_text_hashes: set[str] = set()

    for document in documents:
        policy = policy_by_site.get(document.site, ProcessingFilterPolicy())
        decision = policy.evaluate_document(document=document, seen_text_hashes=seen_text_hashes)
        if decision.skip:
            filtered.append(
                filter_event(
                    stage="filter_document",
                    reason=decision.reason,
                    site=document.site,
                    source_url=document.source_url,
                    raw_path=document.raw_path,
                    metadata={
                        "doc_id": document.doc_id,
                        "title": document.title,
                        "document_type": document.metadata.get("document_type", ""),
                        "text_chars": len(document.text),
                        **(decision.metadata or {}),
                    },
                )
            )
            continue

        text_hash = (decision.metadata or {}).get("text_hash") or normalized_text_hash(document.text)
        seen_text_hashes.add(str(text_hash))
        kept.append(document)

    return kept, filtered


def filter_chunks(
    chunks: list[Chunk],
    policy_by_site: dict[str, ProcessingFilterPolicy],
) -> tuple[list[Chunk], list[dict]]:
    kept: list[Chunk] = []
    filtered: list[dict] = []
    seen_chunk_hashes: set[str] = set()

    for chunk in chunks:
        policy = policy_by_site.get(chunk.site, ProcessingFilterPolicy())
        text_hash = normalized_text_hash(chunk.text)
        if policy.skip_duplicate_chunks and text_hash in seen_chunk_hashes:
            filtered.append(
                filter_event(
                    stage="filter_chunk",
                    reason="duplicate_chunk_text",
                    site=chunk.site,
                    source_url=chunk.source_url,
                    raw_path=str(chunk.metadata.get("raw_path", "")),
                    metadata={
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "chunk_index": chunk.chunk_index,
                        "text_hash": text_hash,
                    },
                )
            )
            continue

        seen_chunk_hashes.add(text_hash)
        kept.append(chunk)

    return kept, filtered


def filter_event(
    *,
    stage: str,
    reason: str,
    site: str,
    source_url: str,
    raw_path: str | None,
    metadata: dict | None = None,
) -> dict:
    event_metadata = dict(metadata or {})
    if raw_path:
        event_metadata.setdefault("raw_path", raw_path)
    return {
        "site": site,
        "stage": stage,
        "url": source_url,
        "reason": reason,
        "metadata": event_metadata,
    }


def matching_pattern(value: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        if re.search(pattern, value):
            return pattern
    return ""


def pattern_matches_any(value: str, patterns: tuple[str, ...]) -> bool:
    return bool(patterns and matching_pattern(value, patterns))


def normalized_text_hash(text: str) -> str:
    import hashlib

    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()
