from __future__ import annotations

import unittest

from kaist_crawler.models import Chunk, Document
from kaist_crawler.quality_gate import build_quality_gate_report


class QualityGateTests(unittest.TestCase):
    def test_warns_for_missing_dept_and_pdf_heavy_chunks(self) -> None:
        documents = [
            Document(
                doc_id="doc1",
                site="sample",
                source_url="https://example.edu/a.pdf",
                title="A",
                text="text",
                metadata={"document_type": "pdf"},
            )
        ]
        chunks = [
            Chunk(
                chunk_id=f"chunk{i}",
                doc_id="doc1",
                site="sample",
                source_url="https://example.edu/a.pdf",
                text="chunk text",
                chunk_index=i,
                metadata={"source_type": "pdf", "content_type": "general"},
            )
            for i in range(4)
        ]

        report = build_quality_gate_report(
            documents=documents,
            chunks=chunks,
            errors=[{"site": "sample", "stage": "process_pdf_text"}],
            filtered=[],
        )

        self.assertEqual(report.status, "fail")
        self.assertEqual(report.sites[0].status, "fail")
        self.assertTrue(any("missing dept" in warning for warning in report.sites[0].warnings))
        self.assertTrue(any("PDF chunk ratio" in warning for warning in report.sites[0].warnings))

    def test_passes_balanced_chunks_with_required_metadata(self) -> None:
        documents = [
            Document(
                doc_id="doc1",
                site="sample",
                source_url="https://example.edu/faculty",
                title="Faculty",
                text="text",
                metadata={"document_type": "html"},
            )
        ]
        chunks = [
            Chunk(
                chunk_id="chunk1",
                doc_id="doc1",
                site="sample",
                source_url="https://example.edu/faculty",
                text="Professor profile",
                chunk_index=0,
                metadata={"dept": "sample", "source_type": "html", "content_type": "person"},
            )
        ]

        report = build_quality_gate_report(documents=documents, chunks=chunks, errors=[], filtered=[])

        self.assertEqual(report.status, "pass")
        self.assertEqual(report.sites[0].score, 100)


if __name__ == "__main__":
    unittest.main()
