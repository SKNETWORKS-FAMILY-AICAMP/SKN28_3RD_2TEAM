from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.query_analyzer import QuestionAnalyzer, QueryAnalysis
from src.rag.vector_retriever import VectorRetriever, VectorRetrievalResult
from src.rag.context_builder import ContextBuilder, ContextBuilderConfig, BuiltContext, SqlQueryResult
from src.rag.answer_generator import AnswerGenerator, GeneratedAnswer
from src.rag.sql_tool import SQLTool


@dataclass
class RAGPipelineResponse:
    answer: str
    route: str
    status: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RAGPipeline:
    def __init__(
        self,
        analyzer: QuestionAnalyzer | None = None,
        retriever: VectorRetriever | None = None,
        sql_tool: SQLTool | None = None,
        context_builder: ContextBuilder | None = None,
        answer_generator: AnswerGenerator | None = None,
    ) -> None:
        self.analyzer = analyzer or QuestionAnalyzer()
        self.retriever = retriever or VectorRetriever()
        self.sql_tool = sql_tool or SQLTool()
        self.context_builder = context_builder or ContextBuilder(
            ContextBuilderConfig(
                include_debug_info=False,
            )
        )
        self.answer_generator = answer_generator or AnswerGenerator()

    def ask(
        self,
        question: str,
        previous_department_code: str | None = None,
    ) -> RAGPipelineResponse:
        analysis = self.analyzer.analyze(
            question=question,
            previous_department_code=previous_department_code,
        )

        if analysis.route == "clarify":
            return self._clarify_response(analysis)

        vector_result: VectorRetrievalResult | None = None
        sql_result: SqlQueryResult | None = None

        if analysis.route in {"vector", "hybrid"}:
            vector_result = self.retriever.retrieve(
                question=question,
                previous_department_code=previous_department_code,
                force_vector_search=True,
            )

            if vector_result.status == "need_clarification":
                return self._clarify_response(vector_result.analysis)

        if analysis.route in {"sql", "hybrid"}:
            sql_result = self.sql_tool.query(analysis)

        active_analysis = vector_result.analysis if vector_result else analysis

        built_context = self.context_builder.build(
            analysis=active_analysis,
            vector_result=vector_result,
            sql_result=sql_result,
        )

        generated = self.answer_generator.generate(
            question=question,
            built_context=built_context,
            analysis=active_analysis,
        )

        return self._build_response(
            analysis=active_analysis,
            vector_result=vector_result,
            sql_result=sql_result,
            built_context=built_context,
            generated=generated,
        )

    def _clarify_response(
        self,
        analysis: QueryAnalysis,
    ) -> RAGPipelineResponse:
        return RAGPipelineResponse(
            answer=analysis.clarifying_message or "질문을 조금 더 구체적으로 입력해주세요.",
            route=analysis.route,
            status="need_clarification",
            sources=[],
            warnings=[],
            debug={
                "analysis": analysis.to_dict(),
            },
        )

    def _build_response(
        self,
        analysis: QueryAnalysis,
        vector_result: VectorRetrievalResult | None,
        sql_result: SqlQueryResult | None,
        built_context: BuiltContext,
        generated: GeneratedAnswer,
    ) -> RAGPipelineResponse:
        warnings = self._merge_warnings(
            generated_warnings=generated.warnings,
            vector_result=vector_result,
            sql_result=sql_result,
        )

        sources = self._format_sources_for_streamlit(
            vector_result=vector_result,
            sql_result=sql_result,
            generated=generated,
        )

        return RAGPipelineResponse(
            answer=generated.answer,
            route=analysis.route,
            status=self._resolve_status(
                analysis=analysis,
                vector_result=vector_result,
                sql_result=sql_result,
            ),
            sources=sources,
            warnings=warnings,
            debug={
                "analysis": analysis.to_dict(),
                "vector_result": vector_result.to_debug_dict() if vector_result else None,
                "sql_result": self._sql_result_debug(sql_result),
                "context_warnings": built_context.warnings,
            },
        )

    def _resolve_status(
        self,
        analysis: QueryAnalysis,
        vector_result: VectorRetrievalResult | None,
        sql_result: SqlQueryResult | None,
    ) -> str:
        if analysis.route == "sql":
            if sql_result is None:
                return "sql_not_executed"

            if sql_result.warnings:
                return "sql_warning"

            if sql_result.is_empty():
                return "sql_no_result"

            return "sql_searched"

        if analysis.route == "hybrid":
            vector_status = vector_result.status if vector_result else "vector_not_executed"

            if sql_result is None:
                return f"hybrid_{vector_status}_sql_not_executed"

            if sql_result.warnings:
                return f"hybrid_{vector_status}_sql_warning"

            if sql_result.is_empty():
                return f"hybrid_{vector_status}_sql_no_result"

            return f"hybrid_{vector_status}_sql_searched"

        if vector_result:
            return vector_result.status

        return "unknown"

    def _merge_warnings(
        self,
        generated_warnings: list[str],
        vector_result: VectorRetrievalResult | None,
        sql_result: SqlQueryResult | None,
    ) -> list[str]:
        warnings = []

        warnings.extend(generated_warnings)

        if vector_result:
            warnings.extend(vector_result.warnings)

        if sql_result:
            warnings.extend(sql_result.warnings)

        return self._deduplicate_strings(warnings)

    def _format_sources_for_streamlit(
        self,
        vector_result: VectorRetrievalResult | None,
        sql_result: SqlQueryResult | None,
        generated: GeneratedAnswer,
    ) -> list[dict[str, Any]]:
        sources = []

        if vector_result:
            sources.extend(
                self._format_vector_sources_for_streamlit(vector_result)
            )

        if sql_result and not sql_result.is_empty():
            sources.append(
                {
                    "title": f"SQL: {sql_result.table_name}",
                    "meta": f"{sql_result.table_name} · {len(sql_result.rows)} rows · sql",
                    "url": "",
                    "row_count": len(sql_result.rows),
                    "conditions": sql_result.conditions,
                }
            )

        if not sources:
            sources.extend(
                self._format_generated_sources_for_streamlit(generated)
            )

        return sources

    def _format_vector_sources_for_streamlit(
        self,
        vector_result: VectorRetrievalResult,
    ) -> list[dict[str, Any]]:
        sorted_items = sorted(
            vector_result.results,
            key=lambda item: item.rerank_score,
            reverse=True,
        )

        formatted_sources = []
        seen_keys = set()

        for item in sorted_items:
            metadata = item.document.metadata

            title = str(metadata.get("title") or "출처")
            url = str(metadata.get("source") or metadata.get("source_url") or "")
            department = str(metadata.get("dept_name") or metadata.get("department") or "")
            content_type = str(metadata.get("content_type") or metadata.get("doc_type") or "")

            key = (
                title,
                url,
                department,
                content_type,
            )

            if key in seen_keys:
                continue

            seen_keys.add(key)

            meta_parts = [
                part
                for part in [department, content_type, "vector"]
                if part
            ]

            formatted_sources.append(
                {
                    "title": title,
                    "meta": " · ".join(meta_parts),
                    "url": url,
                    "score": item.score,
                    "rerank_score": item.rerank_score,
                    "search_stage": item.search_stage,
                }
            )

        return formatted_sources

    def _format_generated_sources_for_streamlit(
        self,
        generated: GeneratedAnswer,
    ) -> list[dict[str, Any]]:
        formatted_sources = []
        seen_keys = set()

        for source in generated.sources:
            title = source.title or "출처"
            url = source.source or ""
            department = source.department or ""
            content_type = source.content_type or ""

            key = (
                source.source_type,
                title,
                url,
                department,
                content_type,
            )

            if key in seen_keys:
                continue

            seen_keys.add(key)

            meta_parts = [
                part
                for part in [department, content_type, source.source_type]
                if part
            ]

            formatted_sources.append(
                {
                    "title": title,
                    "meta": " · ".join(meta_parts),
                    "url": url,
                }
            )

        return formatted_sources

    def _sql_result_debug(
        self,
        sql_result: SqlQueryResult | None,
    ) -> dict[str, Any] | None:
        if sql_result is None:
            return None

        return {
            "table_name": sql_result.table_name,
            "row_count": len(sql_result.rows),
            "columns": sql_result.columns,
            "conditions": sql_result.conditions,
            "message": sql_result.message,
            "warnings": sql_result.warnings,
            "rows_preview": sql_result.rows[:5],
        }

    def _deduplicate_strings(
        self,
        values: list[str],
    ) -> list[str]:
        seen = set()
        results = []

        for value in values:
            if not value:
                continue

            if value in seen:
                continue

            seen.add(value)
            results.append(value)

        return results


def run_examples() -> None:
    pipeline = RAGPipeline()

    questions = [
        "AI컴퓨팅학과 석사 지원 자격은?",
        "AI컴퓨팅학과 박사 지원 자격은?",
        "AI컴퓨팅학과 석박사 통합과정 지원 자격은?",
        "AI컴퓨팅학과 학과설명회 정보 알려줘",
        "AI시스템학과 교과목 알려줘",
        "AI시스템학과 교과목 목록과 각 과목 설명도 알려줘",
        "AX학과 교수진 이메일 목록 보여줘",
        "AX학과 교수 연구분야도 설명해줘",
        "교수진도 알려줘",
    ]

    for question in questions:
        result = pipeline.ask(question)

        print("=" * 100)
        print("질문:", question)
        print("route:", result.route)
        print("status:", result.status)
        print("answer:", result.answer)
        print("sources:", result.sources)
        print("warnings:", result.warnings)


if __name__ == "__main__":
    run_examples()