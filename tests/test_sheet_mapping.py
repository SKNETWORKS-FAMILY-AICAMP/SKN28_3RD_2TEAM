from __future__ import annotations

import unittest
from pathlib import Path

from kaist_crawler.adapters import fill_route_pattern, parse_google_sheet_source, sheet_route_value
from kaist_crawler.models import Document, RawRecord, SourceConfig
from kaist_crawler.processor import add_sheet_row_documents
from kaist_crawler.sheet_mapping import sheet_row_documents
from kaist_crawler.vector_store import default_collection_name


class SheetMappingTests(unittest.TestCase):
    def test_dynamic_route_source_is_parsed_from_config(self) -> None:
        self.assertEqual(
            parse_google_sheet_source("google_sheet:faculty.name_en_slug"),
            ("faculty", "name_en_slug"),
        )
        self.assertIsNone(parse_google_sheet_source("api:faculty.name"))

    def test_dynamic_route_value_can_slugify_derived_field(self) -> None:
        row = {"name_en": "Jane Doe"}

        self.assertEqual(sheet_route_value(row, "name_en_slug"), "jane-doe")
        self.assertEqual(fill_route_pattern("/faculty-card/{slug}", "jane-doe"), "/faculty-card/jane-doe")

    def test_sheet_row_documents_are_created_from_mapping(self) -> None:
        source = SourceConfig(
            id="sample",
            name="Sample Graduate School",
            base_url="https://example.edu/",
            adapter="vite_react_spa_with_google_sheets",
            google_sheets={
                "document_mappings": {
                    "notice": {
                        "document_type": "notice",
                        "route_template": "/notice/{slug}",
                        "slug_field": "slug",
                        "title_fields": ["title"],
                        "text_fields": ["title", "body"],
                        "metadata_fields": ["category"],
                    }
                }
            },
        )
        record = RawRecord(
            source_id="sample:sheet",
            site="sample",
            adapter=source.adapter,
            source_url="https://docs.example/sheet",
            canonical_url="https://docs.example/sheet",
            content_type="application/json",
            raw_path="raw/sample/sheets/notice.json",
            sha256="abc",
            fetched_at="2026-06-17T00:00:00+09:00",
        )
        documents: list[Document] = []

        add_sheet_row_documents(
            documents,
            source=source,
            record=record,
            raw_path=Path(record.raw_path),
            sheet_name="notice",
            rows=[{"slug": "fall-admission", "title": "Fall Admission", "body": "Apply now", "category": "admission"}],
        )

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].source_url, "https://example.edu/notice/fall-admission")
        self.assertEqual(documents[0].metadata["document_type"], "notice")
        self.assertEqual(documents[0].metadata["category"], "admission")

    def test_sheet_row_mapper_returns_specs_without_processor_dependency(self) -> None:
        source = SourceConfig(
            id="sample",
            name="Sample Graduate School",
            base_url="https://example.edu/",
            adapter="vite_react_spa_with_google_sheets",
            google_sheets={
                "document_mappings": {
                    "faculty": {
                        "document_type": "faculty",
                        "route_template": "/faculty/{slug}",
                        "slug_field": "name_en_slug",
                        "title_fields": ["name_ko", "name_en"],
                    }
                }
            },
        )
        record = RawRecord(
            source_id="sample:sheet",
            site="sample",
            adapter=source.adapter,
            source_url="https://docs.example/sheet",
            canonical_url="https://docs.example/sheet",
            content_type="application/json",
            raw_path="raw/sample/sheets/faculty.json",
            sha256="abc",
            fetched_at="2026-06-17T00:00:00+09:00",
        )

        documents = sheet_row_documents(
            source=source,
            record=record,
            raw_path=Path(record.raw_path),
            sheet_name="faculty",
            rows=[{"name_ko": "Kim", "name_en": "Jane Kim", "research": "AI"}],
        )

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].source_url, "https://example.edu/faculty/jane-kim")
        self.assertEqual(documents[0].title, "Kim")
        self.assertEqual(documents[0].metadata["document_type"], "faculty")

    def test_default_collection_name_is_not_kaist_specific(self) -> None:
        name = default_collection_name(provider="openai", model="text-embedding-3-large", dimensions=3072)

        self.assertTrue(name.startswith("graduate_rag_openai_"))
        self.assertNotIn("kaist", name.lower())


if __name__ == "__main__":
    unittest.main()
