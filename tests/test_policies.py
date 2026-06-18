from __future__ import annotations

import unittest
from pathlib import Path

from kaist_crawler.models import Chunk, Document, RawRecord
from kaist_crawler.policies import (
    FilePolicy,
    ProcessingFilterPolicy,
    filter_chunks,
    filter_documents,
)


class FilePolicyTests(unittest.TestCase):
    def test_excludes_matching_url_pattern(self) -> None:
        policy = FilePolicy(exclude_url_patterns=(r"(?i)newsletter",))

        decision = policy.evaluate(
            requested_url="https://example.edu/files/newsletter.pdf",
            content_length=1024,
            content_type="application/pdf",
        )

        self.assertTrue(decision.skip)
        self.assertEqual(decision.reason, "excluded_url_pattern")

    def test_rejects_file_over_size_limit(self) -> None:
        policy = FilePolicy(max_file_size_mb=30)

        decision = policy.evaluate(
            requested_url="https://example.edu/files/admission.pdf",
            content_length=31 * 1024 * 1024,
            content_type="application/pdf",
        )

        self.assertTrue(decision.skip)
        self.assertEqual(decision.reason, "file_too_large")

    def test_include_pattern_overrides_exclude_and_size_limit(self) -> None:
        policy = FilePolicy(
            max_file_size_mb=30,
            exclude_url_patterns=(r"(?i)newsletter",),
            include_url_patterns=(r"(?i)must-keep",),
        )

        decision = policy.evaluate(
            requested_url="https://example.edu/files/must-keep-newsletter.pdf",
            content_length=100 * 1024 * 1024,
            content_type="application/pdf",
        )

        self.assertFalse(decision.skip)

    def test_excludes_matching_link_context_pattern(self) -> None:
        policy = FilePolicy(exclude_context_patterns=(r"(?i)seminar",))

        decision = policy.evaluate(
            requested_url="https://example.edu/files/notice.pdf",
            content_length=1024,
            content_type="application/pdf",
            context="Weekly seminar handout",
        )

        self.assertTrue(decision.skip)
        self.assertEqual(decision.reason, "excluded_context_pattern")

    def test_include_context_pattern_overrides_exclude_context(self) -> None:
        policy = FilePolicy(
            exclude_context_patterns=(r"(?i)seminar",),
            include_context_patterns=(r"(?i)graduate admission",),
        )

        decision = policy.evaluate(
            requested_url="https://example.edu/files/guide.pdf",
            content_length=1024,
            content_type="application/pdf",
            context="Graduate admission seminar guide",
        )

        self.assertFalse(decision.skip)


class ProcessingFilterPolicyTests(unittest.TestCase):
    def test_excludes_pdf_by_url_pattern_before_text_extraction(self) -> None:
        raw_path = Path("raw/site/files/newsletter.pdf")
        record = RawRecord(
            source_id="site:1",
            site="site",
            adapter="static_html",
            source_url="https://example.edu/newsletter.pdf",
            canonical_url="https://example.edu/newsletter.pdf",
            content_type="application/pdf",
            raw_path=str(raw_path),
            sha256="abc",
            fetched_at="2026-06-17T00:00:00+09:00",
        )
        policy = ProcessingFilterPolicy(exclude_pdf_url_patterns=(r"(?i)newsletter",))

        decision = policy.evaluate_raw_record(
            record=record,
            raw_path=raw_path,
            category="files",
            seen_sha=set(),
        )

        self.assertTrue(decision.skip)
        self.assertEqual(decision.reason, "excluded_pdf_pattern")

    def test_html_include_policy_keeps_only_matching_pages(self) -> None:
        policy = ProcessingFilterPolicy(
            min_text_chars=1,
            include_html_url_patterns=(r"/admission/",),
        )
        documents = [
            Document(
                doc_id="doc:admission",
                site="site",
                source_url="https://example.edu/admission/apply.html",
                title="Admission",
                text="Admission text",
                metadata={"document_type": "html"},
            ),
            Document(
                doc_id="doc:campus",
                site="site",
                source_url="https://example.edu/campus/map.html",
                title="Campus",
                text="Campus text",
                metadata={"document_type": "html"},
            ),
        ]

        kept, filtered = filter_documents(documents, {"site": policy})

        self.assertEqual([doc.doc_id for doc in kept], ["doc:admission"])
        self.assertEqual(filtered[0]["reason"], "html_not_included_by_policy")

    def test_duplicate_chunks_are_filtered(self) -> None:
        chunks = [
            Chunk(
                chunk_id="chunk:1",
                doc_id="doc:1",
                site="site",
                source_url="https://example.edu/a",
                text="Same chunk text",
                chunk_index=0,
            ),
            Chunk(
                chunk_id="chunk:2",
                doc_id="doc:2",
                site="site",
                source_url="https://example.edu/b",
                text="Same   chunk\ntext",
                chunk_index=0,
            ),
        ]

        kept, filtered = filter_chunks(chunks, {"site": ProcessingFilterPolicy()})

        self.assertEqual([chunk.chunk_id for chunk in kept], ["chunk:1"])
        self.assertEqual(filtered[0]["reason"], "duplicate_chunk_text")


if __name__ == "__main__":
    unittest.main()
