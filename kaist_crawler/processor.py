from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from .extractors import (
    chunk_documents,
    html_to_sections,
    js_literal_text,
    parse_gviz,
    pdf_to_text,
    sheet_rows_to_text,
)
from .models import Chunk, Document, RawRecord, SourceConfig
from .policies import ProcessingFilterPolicy, filter_chunks, filter_documents, filter_event
from .rag_metadata import infer_section_title, normalize_rag_metadata
from .rag_relevance import classify_documents
from .sheet_mapping import sheet_row_documents
from .store import safe_filename, stable_id


def process_raw_documents(
    *,
    output_root: str | Path,
    sources: list[SourceConfig],
    use_llm_relevance: bool = False,
    relevance_model: str | None = None,
    max_llm_relevance: int | None = None,
) -> tuple[list[Document], list[Chunk], list[dict], list[dict]]:
    output_root = Path(output_root)
    source_by_id = {source.id: source for source in sources}
    policy_by_site = {
        source.id: ProcessingFilterPolicy.from_options(source.processing_options.get("filter_policy", {}))
        for source in sources
    }
    records, errors = load_raw_records(output_root=output_root, sources=sources)
    documents: list[Document] = []
    filtered: list[dict] = []
    bundle_texts_by_site: dict[str, list[str]] = defaultdict(list)
    seen_bundle_texts: set[tuple[str, str]] = set()
    seen_raw_sha: set[str] = set()

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

        policy = policy_by_site.get(record.site, ProcessingFilterPolicy())
        decision = policy.evaluate_raw_record(
            record=record,
            raw_path=raw_path,
            category=raw_category(record),
            seen_sha=seen_raw_sha,
        )
        if decision.skip:
            filtered.append(
                filter_event(
                    stage="filter_raw_record",
                    reason=decision.reason,
                    site=record.site,
                    source_url=record.canonical_url,
                    raw_path=str(raw_path.as_posix()),
                    metadata=decision.metadata,
                )
            )
            continue
        seen_raw_sha.add(record.sha256)

        try:
            process_raw_record(
                documents=documents,
                errors=errors,
                bundle_texts_by_site=bundle_texts_by_site,
                seen_bundle_texts=seen_bundle_texts,
                source=source,
                record=record,
                raw_path=raw_path,
            )
        except Exception as exc:
            errors.append(processing_error(stage="process_raw_record", record=record, error=exc))

    add_spa_bundle_documents(documents, bundle_texts_by_site=bundle_texts_by_site, source_by_id=source_by_id)

    documents, document_filter_events = filter_documents(documents, policy_by_site)
    filtered.extend(document_filter_events)
    classify_documents(
        documents,
        use_llm=use_llm_relevance,
        llm_model=relevance_model,
        max_llm=max_llm_relevance,
        cache_path=output_root / ".cache" / "relevance_cache.jsonl",
    )
    chunks = chunk_documents(documents)
    chunks, chunk_filter_events = filter_chunks(chunks, policy_by_site)
    filtered.extend(chunk_filter_events)
    return documents, chunks, errors, filtered


def process_raw_record(
    *,
    documents: list[Document],
    errors: list[dict],
    bundle_texts_by_site: dict[str, list[str]],
    seen_bundle_texts: set[tuple[str, str]],
    source: SourceConfig,
    record: RawRecord,
    raw_path: Path,
) -> None:
    category = raw_category(record)
    suffix = raw_path.suffix.lower()
    content_type = record.content_type.lower()
    if category == "pages" and ("html" in content_type or suffix in {"", ".html", ".htm"}):
        process_html_record(documents, source=source, record=record, raw_path=raw_path)
    elif category == "assets" and (suffix == ".js" or "javascript" in content_type):
        collect_spa_bundle_text(
            bundle_texts_by_site=bundle_texts_by_site,
            seen_bundle_texts=seen_bundle_texts,
            record=record,
            raw_path=raw_path,
        )
    elif category == "sheets":
        process_sheet_record(documents, source=source, record=record, raw_path=raw_path)
    elif category == "files" and suffix == ".pdf":
        process_pdf_record(documents, errors, source=source, record=record, raw_path=raw_path)


def collect_spa_bundle_text(
    *,
    bundle_texts_by_site: dict[str, list[str]],
    seen_bundle_texts: set[tuple[str, str]],
    record: RawRecord,
    raw_path: Path,
) -> None:
    text = js_literal_text(read_text(raw_path))
    key = (record.site, text)
    if text and key not in seen_bundle_texts:
        seen_bundle_texts.add(key)
        bundle_texts_by_site[record.site].append(text)


def add_spa_bundle_documents(
    documents: list[Document],
    *,
    bundle_texts_by_site: dict[str, list[str]],
    source_by_id: dict[str, SourceConfig],
) -> None:
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
            metadata=source_scope_metadata(source, {"document_type": "spa_bundle_text"}),
        )


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
    metadata = source_scope_metadata(source, record.metadata)
    document_type = html_document_type(source, metadata)
    if document_type is None:
        return
    title, sections = html_to_sections(read_text(raw_path))
    for section_index, section in enumerate(sections):
        section_metadata = dict(metadata)
        section_metadata["document_type"] = document_type
        section_metadata["section_index"] = section_index
        if section.title:
            section_metadata["section"] = section.title
        add_document(
            documents,
            site=record.site,
            source_url=record.canonical_url,
            title=section.title or title or source.name,
            text=section.text,
            raw_path=str(raw_path.as_posix()),
            metadata=section_metadata,
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
            metadata=source_scope_metadata(source, {"document_type": "google_sheet", "sheet": sheet_name}),
        )
    add_sheet_row_documents(documents, source=source, record=record, raw_path=raw_path, sheet_name=sheet_name, rows=rows)


def process_pdf_record(
    documents: list[Document],
    errors: list[dict],
    *,
    source: SourceConfig,
    record: RawRecord,
    raw_path: Path,
) -> None:
    pdf_result = pdf_to_text(raw_path)
    file_name = safe_filename(urlparse(record.canonical_url).path, "pdf")
    if pdf_result.text:
        page_texts = pdf_result.page_texts or (pdf_result.text,)
        for page_index, page_text in enumerate(page_texts, start=1):
            if not page_text.strip():
                continue
            add_document(
                documents,
                site=record.site,
                source_url=record.canonical_url,
                title=file_name,
                text=page_text,
                raw_path=str(raw_path.as_posix()),
                metadata=source_scope_metadata(
                    source,
                    {
                        "document_type": "pdf",
                        "pdf_extractor": pdf_result.extractor,
                        "pdf_pages": pdf_result.pages,
                        "page": page_index,
                        "section": infer_section_title(page_text, fallback=file_name),
                        "file_name": file_name,
                    },
                ),
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


def add_sheet_row_documents(
    documents: list[Document],
    *,
    source: SourceConfig,
    record: RawRecord,
    raw_path: Path,
    sheet_name: str,
    rows: list[dict[str, str]],
) -> None:
    for document in sheet_row_documents(
        source=source,
        record=record,
        raw_path=raw_path,
        sheet_name=sheet_name,
        rows=rows,
    ):
        add_document(
            documents,
            site=record.site,
            source_url=document.source_url,
            title=document.title,
            text=document.text,
            raw_path=document.raw_path,
            metadata=source_scope_metadata(source, document.metadata),
        )


def source_scope_metadata(source: SourceConfig, metadata: dict | None = None) -> dict:
    result = dict(metadata or {})
    if source.institution:
        result.setdefault("institution", source.institution)
    if source.institution_name:
        result.setdefault("institution_name", source.institution_name)
    if source.college:
        result.setdefault("college", source.college)
    if source.college_name:
        result.setdefault("college_name", source.college_name)
    if source.dept:
        result.setdefault("dept", source.dept)
    if source.dept_name:
        result.setdefault("dept_name", source.dept_name)
    return result


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
    metadata = normalize_rag_metadata(
        site=site,
        source_url=source_url,
        title=title,
        text=text,
        metadata=metadata,
    )
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
