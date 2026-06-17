from __future__ import annotations

import unittest

from kaist_crawler.models import Document
from kaist_crawler.extractors import chunk_documents, split_text_by_headings
from kaist_crawler.rag_metadata import normalize_rag_metadata
from kaist_crawler.retrieval import analyze_retrieval_query, build_filter_plan


class RagMetadataTests(unittest.TestCase):
    def test_normalizes_department_and_admission_content_type_from_site_and_route(self) -> None:
        metadata = normalize_rag_metadata(
            site="kaist_ax",
            source_url="https://ax.kaist.ac.kr/admission-grad",
            title="대학원 입학 안내",
            text="석사 박사 모집 및 지원 자격 안내",
            metadata={"document_type": "html", "route": "/admission-grad"},
        )

        self.assertEqual(metadata["dept"], "ax")
        self.assertEqual(metadata["dept_name"], "AX학과")
        self.assertEqual(metadata["source_type"], "html")
        self.assertEqual(metadata["content_type"], "admission")

    def test_reclassifies_faculty_sheet_row_as_person(self) -> None:
        metadata = normalize_rag_metadata(
            site="kaist_fx",
            source_url="https://fx.kaist.ac.kr/faculty-card/nuri-kim",
            title="김누리",
            text="name_ko: 김누리\nresearchInterests_ko: AI와 사회",
            metadata={"document_type": "faculty"},
        )

        self.assertEqual(metadata["dept"], "fx")
        self.assertEqual(metadata["source_type"], "faculty")
        self.assertEqual(metadata["content_type"], "person")

    def test_unknown_site_uses_source_id_dept_before_keyword_detection(self) -> None:
        metadata = normalize_rag_metadata(
            site="kaist_physics",
            source_url="https://physics.kaist.ac.kr/",
            title="Physics",
            text="AI seminar and admission notice",
            metadata={"document_type": "html"},
        )

        self.assertEqual(metadata["dept"], "physics")
        self.assertEqual(metadata["dept_name"], "Physics")

    def test_chunking_reclassifies_by_chunk_text_and_preserves_page(self) -> None:
        document = Document(
            doc_id="doc1",
            site="kaist_ai_systems",
            source_url="https://ai-systems.kaist.ac.kr/attachments/info.pdf",
            title="AI Systems Grad Info",
            text="지원 자격\n석사과정 지원 자격 안내입니다.\n" * 20,
            metadata={"document_type": "pdf", "page": 3, "section": "지원 자격"},
        )

        chunks = chunk_documents([document], chunk_size=300, overlap=40)

        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(chunks[0].metadata["dept"], "ai_systems")
        self.assertEqual(chunks[0].metadata["content_type"], "admission")
        self.assertEqual(chunks[0].metadata["page"], 3)
        self.assertEqual(chunks[0].metadata["section"], "지원 자격")

    def test_html_text_can_split_by_heading_lines(self) -> None:
        sections = split_text_by_headings(
            "입학 안내\n지원 자격입니다.\n교과목\n교육과정입니다.",
            ["입학 안내", "교과목"],
        )

        self.assertEqual([section.title for section in sections], ["입학 안내", "교과목"])


class RetrievalAnalysisTests(unittest.TestCase):
    def test_query_analysis_detects_department_and_content_type(self) -> None:
        analysis = analyze_retrieval_query("AI미래학과 교수진은?")

        self.assertEqual(analysis.dept, "fx")
        self.assertIn("person", analysis.content_types)

    def test_filter_plan_uses_strict_filter_before_fallbacks(self) -> None:
        analysis = analyze_retrieval_query("AX학과 입시설명회 요약해줘")
        plan = build_filter_plan(analysis)

        self.assertEqual(plan[0][0], "strict_filter")
        self.assertIn(("department_only", {"dept": "ax"}), plan)
        self.assertEqual(plan[-1], ("no_filter", None))


if __name__ == "__main__":
    unittest.main()
