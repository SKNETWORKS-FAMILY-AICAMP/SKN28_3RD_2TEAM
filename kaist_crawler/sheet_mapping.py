from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from .extractors import slugify
from .models import RawRecord, SourceConfig


@dataclass(frozen=True)
class SheetRowDocument:
    source_url: str
    title: str
    text: str
    raw_path: str
    metadata: dict


def sheet_row_documents(
    *,
    source: SourceConfig,
    record: RawRecord,
    raw_path: Path,
    sheet_name: str,
    rows: list[dict[str, str]],
) -> list[SheetRowDocument]:
    mapping = sheet_document_mapping(source, sheet_name)
    if mapping is None:
        return []

    document_type = str(mapping.get("document_type") or sheet_name)
    route_template = str(mapping.get("route_template") or "")
    title_fields = list(mapping.get("title_fields", []))
    text_fields = mapping.get("text_fields", "*")
    metadata_fields = list(mapping.get("metadata_fields", []))
    slug_field = str(mapping.get("slug_field") or "")
    slugify_slug = bool(mapping.get("slugify_slug", False))

    documents: list[SheetRowDocument] = []
    for row in rows:
        slug = row_mapping_slug(row, slug_field=slug_field, slugify_slug=slugify_slug)
        title = first_row_value(row, title_fields) or slug or sheet_name
        body = row_mapping_text(row, text_fields)
        if not body:
            continue

        metadata = {"document_type": document_type, "sheet": sheet_name}
        if slug:
            metadata["slug"] = slug
        for field in metadata_fields:
            value = row.get(field, "").strip()
            if value:
                metadata[field] = value

        documents.append(
            SheetRowDocument(
                source_url=row_mapping_url(
                    source.base_url,
                    route_template=route_template,
                    slug=slug,
                    fallback=record.canonical_url,
                ),
                title=title,
                text=body,
                raw_path=str(raw_path.as_posix()),
                metadata=metadata,
            )
        )
    return documents


def sheet_document_mapping(source: SourceConfig, sheet_name: str) -> dict | None:
    mappings = source.google_sheets.get("document_mappings", {})
    mapping = mappings.get(sheet_name) if isinstance(mappings, dict) else None
    return mapping if isinstance(mapping, dict) else None


def row_mapping_slug(row: dict[str, str], *, slug_field: str, slugify_slug: bool) -> str:
    if not slug_field:
        return ""
    value = row.get(slug_field, "").strip()
    if not value and slug_field.endswith("_slug"):
        value = row.get(slug_field.removesuffix("_slug"), "").strip()
        slugify_slug = True
    if not value:
        return ""
    return slugify(value) if slugify_slug else value


def first_row_value(row: dict[str, str], fields: list[str]) -> str:
    for field in fields:
        value = row.get(field, "").strip()
        if value:
            return value
    return ""


def row_mapping_text(row: dict[str, str], fields: object) -> str:
    if fields == "*" or fields is None:
        return "\n".join(f"{key}: {value}" for key, value in row.items() if value)
    if not isinstance(fields, list):
        return ""
    return "\n\n".join(row.get(field, "").strip() for field in fields if row.get(field, "").strip())


def row_mapping_url(base_url: str, *, route_template: str, slug: str, fallback: str) -> str:
    if not route_template or not slug:
        return fallback
    return urljoin(base_url, re.sub(r"{[^{}]+}", slug, route_template))
