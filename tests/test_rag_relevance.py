from __future__ import annotations

import unittest

from kaist_crawler.models import Document
from kaist_crawler.rag_relevance import RelevanceDecision, classify_document


class RagRelevanceTests(unittest.TestCase):
    def test_admission_document_is_vector_candidate(self) -> None:
        document = Document(
            doc_id="doc:admission",
            site="sample",
            source_url="https://example.edu/admission",
            title="대학원 입학 안내",
            text="석사 박사 지원 자격과 전형 일정 안내입니다.",
            metadata={"content_type": "admission", "source_type": "html"},
        )

        decision = classify_document(document)

        self.assertTrue(decision.vector_candidate)
        self.assertGreaterEqual(decision.rag_priority, 90)
        self.assertEqual(decision.content_type, "admission")

    def test_old_exam_pdf_is_not_vector_candidate(self) -> None:
        document = Document(
            doc_id="doc:oldexam",
            site="sample",
            source_url="https://example.edu/resource/oldexam/Midterm.pdf",
            title="Midterm",
            text="Past exam questions",
            metadata={"content_type": "general", "source_type": "pdf", "document_type": "pdf"},
        )

        decision = classify_document(document)

        self.assertFalse(decision.vector_candidate)
        self.assertEqual(decision.content_type, "old_exam")

    def test_ambiguous_document_can_use_llm_decision(self) -> None:
        document = Document(
            doc_id="doc:ambiguous",
            site="sample",
            source_url="https://example.edu/notice/123",
            title="Notice",
            text="This page contains graduate school counseling policy details.",
            metadata={"content_type": "general", "source_type": "html"},
        )

        decision = classify_document(document, llm_client=FakeLlmClient())

        self.assertTrue(decision.vector_candidate)
        self.assertEqual(decision.source, "llm")
        self.assertEqual(decision.content_type, "academic_policy")


class FakeLlmClient:
    def classify(self, document: Document) -> RelevanceDecision:
        return RelevanceDecision(
            vector_candidate=True,
            rag_priority=80,
            content_type="academic_policy",
            reason="Useful academic policy for counseling.",
            source="llm",
            label="llm_decision",
            needs_llm=True,
        )


if __name__ == "__main__":
    unittest.main()
