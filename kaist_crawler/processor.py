from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .extractors import (
    chunk_documents,
    html_to_text,
    js_literal_text,
    parse_gviz,
    pdf_to_text,
    sheet_rows_to_text,
    slugify,
)
from .models import Chunk, Document, RawRecord, SourceConfig
from .store import safe_filename, stable_id


def process_raw_documents(
    *,
    output_root: str | Path,
    sources: list[SourceConfig],
) -> tuple[list[Document], list[Chunk], list[dict]]:
    output_root = Path(output_root)
    source_by_id = {source.id: source for source in sources}
    records, errors = load_raw_records(output_root=output_root, sources=sources)
    documents: list[Document] = []
    bundle_texts_by_site: dict[str, list[str]] = defaultdict(list)
    seen_bundle_texts: set[tuple[str, str]] = set()

    for record in records:
        source = source_by_id.get(record.site)
        if source is None:
            continue
        raw_path = resolve_raw_path(record, output_root)
        if not raw_path.exists():
            errors.append(
                processing_error(
                    stage="process_missing_raw_file",
                    record=record,
                    error=FileNotFoundError(str(raw_path)),
                )
            )
            continue

        category = raw_category(record)
        suffix = raw_path.suffix.lower()
        content_type = record.content_type.lower()
        try:
            if category == "pages" and ("html" in content_type or suffix in {"", ".html", ".htm"}):
                process_html_record(documents, source=source, record=record, raw_path=raw_path)
            elif category == "assets" and (suffix == ".js" or "javascript" in content_type):
                text = js_literal_text(read_text(raw_path))
                key = (record.site, text)
                if text and key not in seen_bundle_texts:
                    seen_bundle_texts.add(key)
                    bundle_texts_by_site[record.site].append(text)
            elif category == "sheets":
                process_sheet_record(documents, source=source, record=record, raw_path=raw_path)
            elif category == "files" and suffix == ".pdf":
                process_pdf_record(documents, errors, source=source, record=record, raw_path=raw_path)
        except Exception as exc:
            errors.append(processing_error(stage="process_raw_record", record=record, error=exc))

    for site, texts in bundle_texts_by_site.items():
        source = source_by_id.get(site)
        if source is None or not texts:
            continue
        add_document(
            documents,
            site=site,
            source_url=source.base_url,
            title=f"{source.name} SPA bundle text",
            text="\n\n".join(texts),
            raw_path=None,
            metadata={"document_type": "spa_bundle_text"},
        )

    chunks = chunk_documents(documents)
    return documents, chunks, errors


def load_raw_records(
    *,
    output_root: Path,
    sources: list[SourceConfig],
) -> tuple[list[RawRecord], list[dict]]:
    raw_root = output_root / "raw"
    records: list[RawRecord] = []
    errors: list[dict] = []
    seen_source_ids: set[str] = set()
    for source in sources:
        manifest_path = raw_root / source.id / "manifest.jsonl"
        if not manifest_path.exists():
            errors.append(
                {
                    "site": source.id,
                    "stage": "read_manifest",
                    "url": source.base_url,
                    "error_type": "FileNotFoundError",
                    "error": f"Missing manifest: {manifest_path}",
                    "metadata": {"manifest_path": str(manifest_path)},
                }
            )
            continue
        with manifest_path.open("r", encoding="utf-8") as manifest:
            for line_number, line in enumerate(manifest, start=1):
                if not line.strip():
                    continue
                try:
                    record = RawRecord(**json.loads(line))
                except Exception as exc:
                    errors.append(
                        {
                            "site": source.id,
                            "stage": "read_manifest_record",
                            "url": source.base_url,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "metadata": {
                                "manifest_path": str(manifest_path),
                                "line_number": line_number,
                            },
                        }
                    )
                    continue
                if record.source_id in seen_source_ids:
                    continue
                seen_source_ids.add(record.source_id)
                records.append(record)
    return records, errors


def process_html_record(
    documents: list[Document],
    *,
    source: SourceConfig,
    record: RawRecord,
    raw_path: Path,
) -> None:
    metadata = dict(record.metadata)
    document_type = html_document_type(source, metadata)
    if document_type is None:
        return
    title, text = html_to_text(read_text(raw_path))
    metadata["document_type"] = document_type
    add_document(
        documents,
        site=record.site,
        source_url=record.canonical_url,
        title=title or source.name,
        text=text,
        raw_path=str(raw_path.as_posix()),
        metadata=metadata,
    )


def html_document_type(source: SourceConfig, metadata: dict) -> str | None:
    if source.adapter == "static_html":
        return "html"
    if metadata.get("rendered") is True:
        return "rendered_html"
    if metadata.get("route") == "/":
        return "html_shell"
    return None


def process_sheet_record(
    documents: list[Document],
    *,
    source: SourceConfig,
    record: RawRecord,
    raw_path: Path,
) -> None:
    sheet_name = str(record.metadata.get("sheet") or raw_path.stem)
    rows = parse_gviz(read_text(raw_path))
    if rows:
        add_document(
            documents,
            site=record.site,
            source_url=record.canonical_url,
            title=f"{source.name} {sheet_name} sheet",
            text=sheet_rows_to_text(rows),
            raw_path=str(raw_path.as_posix()),
            metadata={"document_type": "google_sheet", "sheet": sheet_name},
        )
    if source.adapter != "vite_react_spa_with_google_sheets":
        return
    if sheet_name == "news":
        add_news_documents(documents, source=source, record=record, raw_path=raw_path, rows=rows)
    elif sheet_name == "faculty":
        add_faculty_documents(documents, source=source, record=record, raw_path=raw_path, rows=rows)


def process_pdf_record(
    documents: list[Document],
    errors: list[dict],
    *,
    source: SourceConfig,
    record: RawRecord,
    raw_path: Path,
) -> None:
    pdf_result = pdf_to_text(raw_path)
    if pdf_result.text:
        add_document(
            documents,
            site=record.site,
            source_url=record.canonical_url,
            title=safe_filename(urlparse(record.canonical_url).path, "pdf"),
            text=pdf_result.text,
            raw_path=str(raw_path.as_posix()),
            metadata={
                "document_type": "pdf",
                "pdf_extractor": pdf_result.extractor,
                "pdf_pages": pdf_result.pages,
            },
        )
    elif pdf_result.error:
        errors.append(
            processing_error(
                stage="process_pdf_text",
                record=record,
                error=RuntimeError(pdf_result.error),
                metadata={"raw_path": str(raw_path.as_posix()), "site_name": source.name},
            )
        )


def add_news_documents(
    documents: list[Document],
    *,
    source: SourceConfig,
    record: RawRecord,
    raw_path: Path,
    rows: list[dict[str, str]],
) -> None:
    for row in rows:
        slug = row.get("slug", "").strip()
        if not slug:
            continue
        title = row.get("title_ko") or row.get("title_en") or slug
        body = "\n\n".join(
            part
            for part in [
                row.get("title_ko", ""),
                row.get("title_en", ""),
                row.get("body_ko", ""),
                row.get("body_en", ""),
            ]
            if part
        )
        add_document(
            documents,
            site=record.site,
            source_url=urljoin(source.base_url, f"/news/{slug}"),
            title=title,
            text=body,
            raw_path=str(raw_path.as_posix()),
            metadata={"document_type": "news", "slug": slug, "category": row.get("category", "")},
        )


def add_faculty_documents(
    documents: list[Document],
    *,
    source: SourceConfig,
    record: RawRecord,
    raw_path: Path,
    rows: list[dict[str, str]],
) -> None:
    for row in rows:
        name = row.get("name_ko") or row.get("name_en")
        if not name:
            continue
        slug = slugify(row.get("name_en") or name)
        text = "\n".join(f"{key}: {value}" for key, value in row.items() if value)
        add_document(
            documents,
            site=record.site,
            source_url=urljoin(source.base_url, f"/faculty-card/{slug}"),
            title=name,
            text=text,
            raw_path=str(raw_path.as_posix()),
            metadata={"document_type": "faculty", "slug": slug},
        )


def add_document(
    documents: list[Document],
    *,
    site: str,
    source_url: str,
    title: str,
    text: str,
    raw_path: str | None,
    metadata: dict,
) -> None:
    text = text.strip()
    if not text:
        return
    doc_id = f"{site}:{stable_id(source_url, title, raw_path or '', text[:200])}"
    documents.append(
        Document(
            doc_id=doc_id,
            site=site,
            source_url=source_url,
            title=title,
            text=text,
            raw_path=raw_path,
            metadata=metadata,
        )
    )


def resolve_raw_path(record: RawRecord, output_root: Path) -> Path:
    raw_path = Path(record.raw_path)
    candidates = [raw_path]
    if not raw_path.is_absolute():
        candidates.append(Path.cwd() / raw_path)
        candidates.append(output_root / raw_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return raw_path


def raw_category(record: RawRecord) -> str:
    parts = record.raw_path.replace("\\", "/").split("/")
    for index, part in enumerate(parts):
        if part == record.site and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def processing_error(
    *,
    stage: str,
    record: RawRecord,
    error: Exception,
    metadata: dict | None = None,
) -> dict:
    extra_metadata = {"raw_path": record.raw_path}
    if metadata:
        extra_metadata.update(metadata)
    return {
        "site": record.site,
        "stage": stage,
        "url": record.canonical_url,
        "error_type": type(error).__name__,
        "error": str(error),
        "metadata": extra_metadata,
    }

