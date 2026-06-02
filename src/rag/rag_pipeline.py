from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.query_analyzer import QuestionAnalyzer, QueryAnalysis
from src.rag.vector_retriever import VectorRetriever, VectorRetrievalResult

try:
    from src.rag.sql_tool import SQLTool
except Exception:
    SQLTool = None  # type: ignore

try:
    from src.rag.context_builder import ContextBuilder
except Exception:
    ContextBuilder = None  # type: ignore

try:
    from src.rag.answer_generator import AnswerGenerator
except Exception:
    AnswerGenerator = None  # type: ignore


# ============================================================
# 1. 결과 dataclass
# ============================================================

@dataclass
class RagPipelineResult:
    question: str
    answer: str

    analysis: QueryAnalysis
    sources: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    sql_result: Any | None = None
    vector_result: VectorRetrievalResult | None = None
    context: Any | None = None

    debug_context: dict[str, Any] | None = None

    @property
    def intent(self) -> str:
        return self.analysis.intent

    @property
    def route(self) -> str:
        return self.analysis.route

    @property
    def department_code(self) -> str | None:
        return self.analysis.department_code

    @property
    def department_codes(self) -> list[str]:
        return self.analysis.department_codes

    @property
    def needs_clarification(self) -> bool:
        return self.analysis.route == "clarify" or bool(self.analysis.missing_fields)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "intent": self.intent,
            "route": self.route,
            "department_code": self.department_code,
            "department_codes": self.department_codes,
            "needs_clarification": self.needs_clarification,
            "sources": self.sources,
            "warnings": self.warnings,
            "analysis": self.analysis.to_dict(),
            "debug_context": self.debug_context,
        }


# ============================================================
# 2. Pipeline
# ============================================================

class RagPipeline:
    def __init__(
        self,
        question_analyzer: QuestionAnalyzer | None = None,
        sql_retriever: Any | None = None,
        vector_retriever: VectorRetriever | None = None,
        context_builder: Any | None = None,
        answer_generator: Any | None = None,
        include_debug_context: bool = False,
    ) -> None:
        self.question_analyzer = question_analyzer or QuestionAnalyzer()
        self.sql_retriever = sql_retriever
        self.vector_retriever = vector_retriever
        self.context_builder = context_builder
        self.answer_generator = answer_generator
        self.include_debug_context = include_debug_context

    # ------------------------------------------------------------
    # public API
    # ------------------------------------------------------------

    def classify_question(
        self,
        question: str,
        previous_department_code: str | None = None,
    ) -> QueryAnalysis:
        return self.question_analyzer.analyze(
            question=question,
            previous_department_code=previous_department_code,
        )

    def run(
        self,
        question: str,
        previous_department_code: str | None = None,
    ) -> RagPipelineResult:
        analysis = self.classify_question(
            question=question,
            previous_department_code=previous_department_code,
        )

        if analysis.route == "clarify":
            answer = analysis.clarifying_message or "질문을 조금 더 구체적으로 입력해주세요."

            return RagPipelineResult(
                question=question,
                answer=answer,
                analysis=analysis,
                sources=[],
                warnings=[],
                sql_result=None,
                vector_result=None,
                context=None,
                debug_context=self._make_debug_context(
                    analysis=analysis,
                    sql_result=None,
                    vector_result=None,
                    context=None,
                ),
            )

        sql_result = None
        vector_result = None
        warnings: list[str] = []

        if analysis.needs_sql:
            sql_result = self._run_sql(analysis)
            warnings.extend(self._extract_warnings(sql_result))

        if analysis.needs_vector:
            vector_result = self._run_vector(
                question=question,
                analysis=analysis,
                previous_department_code=previous_department_code,
                force_vector_search=True,
            )
            warnings.extend(self._extract_warnings(vector_result))

        # SQL route인데 SQL 결과가 비어 있고, 설명성 fallback이 가능한 질문이면 vector 검색을 보조로 수행
        if (
            analysis.route == "sql"
            and self._is_empty_sql_result(sql_result)
            and self._can_use_vector_fallback_for_sql(analysis)
        ):
            fallback_vector_result = self._run_vector(
                question=question,
                analysis=analysis,
                previous_department_code=previous_department_code,
                force_vector_search=True,
            )

            if fallback_vector_result and fallback_vector_result.status == "searched":
                vector_result = fallback_vector_result
                warnings.append(
                    "SQL 조회 결과가 비어 있어 보조 vector 검색을 수행했습니다. "
                    "답변에는 직접 근거가 있는 내용만 사용해야 합니다."
                )

            warnings.extend(self._extract_warnings(fallback_vector_result))

        context = self._build_context(
            question=question,
            analysis=analysis,
            sql_result=sql_result,
            vector_result=vector_result,
        )

        answer, answer_sources, answer_warnings = self._generate_answer(
            question=question,
            analysis=analysis,
            context=context,
            sql_result=sql_result,
            vector_result=vector_result,
        )

        warnings.extend(answer_warnings)

        sources = self._merge_sources(
            answer_sources=answer_sources,
            sql_result=sql_result,
            vector_result=vector_result,
            context=context,
        )

        warnings = self._deduplicate_strings(warnings)

        return RagPipelineResult(
            question=question,
            answer=answer,
            analysis=analysis,
            sources=sources,
            warnings=warnings,
            sql_result=sql_result,
            vector_result=vector_result,
            context=context,
            debug_context=self._make_debug_context(
                analysis=analysis,
                sql_result=sql_result,
                vector_result=vector_result,
                context=context,
            ),
        )

    def run_streaming(
        self,
        question: str,
        previous_department_code: str | None = None,
        on_token: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> RagPipelineResult:
        """
        Streamlit UI와 평가 코드가 동일한 pipeline 경로를 타게 하기 위한 streaming wrapper.

        현재는 안정성을 위해 내부적으로 run()을 먼저 수행하고,
        완성된 답변을 chunk 단위로 on_token에 전달한다.
        """
        if on_status:
            on_status("질문을 분석하고 있습니다.")

        result = self.run(
            question=question,
            previous_department_code=previous_department_code,
        )

        if on_status:
            on_status("답변을 생성하고 있습니다.")

        if on_token:
            for chunk in self._chunk_answer_for_streaming(result.answer):
                on_token(chunk)

        if on_status:
            on_status("답변 생성이 완료되었습니다.")

        return result

    def search(
        self,
        question: str,
        previous_department_code: str | None = None,
    ) -> dict[str, Any]:
        """
        notebook/debug용 간단 검색 API.
        """
        result = self.run(
            question=question,
            previous_department_code=previous_department_code,
        )
        return result.to_dict()

    # ------------------------------------------------------------
    # SQL / Vector 실행
    # ------------------------------------------------------------

    def _run_sql(self, analysis: QueryAnalysis) -> Any | None:
        if self.sql_retriever is None:
            return {
                "status": "sql_unavailable",
                "message": "SQLTool이 설정되어 있지 않습니다.",
                "rows": [],
                "warnings": ["SQLTool이 설정되어 있지 않습니다."],
            }

        try:
            if hasattr(self.sql_retriever, "query"):
                return self.sql_retriever.query(analysis)

            if hasattr(self.sql_retriever, "search"):
                return self.sql_retriever.search(analysis)

            if callable(self.sql_retriever):
                return self.sql_retriever(analysis)

            return {
                "status": "sql_error",
                "message": "SQL retriever 호출 인터페이스를 찾지 못했습니다.",
                "rows": [],
                "warnings": ["SQL retriever 호출 인터페이스를 찾지 못했습니다."],
            }

        except Exception as exc:
            return {
                "status": "sql_error",
                "message": "SQL 조회 중 오류가 발생했습니다.",
                "rows": [],
                "warnings": [f"{type(exc).__name__}: {exc}"],
            }

    def _run_vector(
        self,
        question: str,
        analysis: QueryAnalysis,
        previous_department_code: str | None,
        force_vector_search: bool,
    ) -> VectorRetrievalResult | None:
        if self.vector_retriever is None:
            return None

        return self.vector_retriever.retrieve(
            question=question,
            previous_department_code=previous_department_code,
            force_vector_search=force_vector_search,
            analysis=analysis,
        )

    # ------------------------------------------------------------
    # Context / Answer
    # ------------------------------------------------------------

    def _build_context(
        self,
        question: str,
        analysis: QueryAnalysis,
        sql_result: Any | None,
        vector_result: VectorRetrievalResult | None,
    ) -> Any:
        """
        ContextBuilder의 기존 구현 차이를 흡수하기 위한 adapter.

        지원하는 형태:
        - build(question=..., analysis=..., sql_result=..., vector_result=...)
        - build(analysis=..., sql_result=..., vector_result=...)
        - build(sql_result, vector_result, analysis)
        - build_context(...)
        - ContextBuilder가 없으면 fallback string context 생성
        """
        if self.context_builder is None:
            return self._build_fallback_context(
                analysis=analysis,
                sql_result=sql_result,
                vector_result=vector_result,
            )

        builder = self.context_builder

        method = None

        if hasattr(builder, "build"):
            method = builder.build
        elif hasattr(builder, "build_context"):
            method = builder.build_context

        if method is None:
            return self._build_fallback_context(
                analysis=analysis,
                sql_result=sql_result,
                vector_result=vector_result,
            )

        call_patterns = [
            lambda: method(
                question=question,
                analysis=analysis,
                sql_result=sql_result,
                vector_result=vector_result,
            ),
            lambda: method(
                analysis=analysis,
                sql_result=sql_result,
                vector_result=vector_result,
            ),
            lambda: method(
                sql_result=sql_result,
                vector_result=vector_result,
                analysis=analysis,
            ),
            lambda: method(sql_result, vector_result, analysis),
            lambda: method(vector_result, sql_result, analysis),
        ]

        last_error: Exception | None = None

        for call in call_patterns:
            try:
                return call()
            except TypeError as exc:
                last_error = exc
                continue

        return {
            "context": self._build_fallback_context(
                analysis=analysis,
                sql_result=sql_result,
                vector_result=vector_result,
            ),
            "warnings": [
                f"ContextBuilder 호출 방식이 맞지 않아 fallback context를 사용했습니다: {last_error}"
            ],
        }

    def _generate_answer(
        self,
        question: str,
        analysis: QueryAnalysis,
        context: Any,
        sql_result: Any | None,
        vector_result: VectorRetrievalResult | None,
    ) -> tuple[str, list[dict[str, Any]], list[str]]:
        if self.answer_generator is None:
            return self._fallback_answer(
                analysis=analysis,
                context=context,
                sql_result=sql_result,
                vector_result=vector_result,
            )

        generator = self.answer_generator

        method = None

        if hasattr(generator, "generate"):
            method = generator.generate
        elif hasattr(generator, "answer"):
            method = generator.answer
        elif callable(generator):
            method = generator

        if method is None:
            return self._fallback_answer(
                analysis=analysis,
                context=context,
                sql_result=sql_result,
                vector_result=vector_result,
            )

        call_patterns = [
            lambda: method(
                question=question,
                analysis=analysis,
                context=context,
                sql_result=sql_result,
                vector_result=vector_result,
            ),
            lambda: method(
                question=question,
                context=context,
                analysis=analysis,
            ),
            lambda: method(question, context, analysis),
            lambda: method(question, context),
        ]

        last_error: Exception | None = None

        for call in call_patterns:
            try:
                raw_result = call()
                return self._normalize_answer_result(raw_result)
            except TypeError as exc:
                last_error = exc
                continue
            except Exception as exc:
                return (
                    "답변 생성 중 오류가 발생했습니다.",
                    [],
                    [f"{type(exc).__name__}: {exc}"],
                )

        fallback_answer, fallback_sources, fallback_warnings = self._fallback_answer(
            analysis=analysis,
            context=context,
            sql_result=sql_result,
            vector_result=vector_result,
        )
        fallback_warnings.append(
            f"AnswerGenerator 호출 방식이 맞지 않아 fallback 답변을 사용했습니다: {last_error}"
        )

        return fallback_answer, fallback_sources, fallback_warnings

    # ------------------------------------------------------------
    # fallback context / answer
    # ------------------------------------------------------------

    def _build_fallback_context(
        self,
        analysis: QueryAnalysis,
        sql_result: Any | None,
        vector_result: VectorRetrievalResult | None,
    ) -> str:
        parts: list[str] = []

        parts.append("[질문 분석]")
        parts.append(f"- route: {analysis.route}")
        parts.append(f"- intent: {analysis.intent}")
        parts.append(f"- department_code: {analysis.department_code}")
        parts.append(f"- department_codes: {analysis.department_codes}")
        parts.append(f"- content_type: {analysis.content_type}")

        rows = self._extract_sql_rows(sql_result)

        if rows:
            parts.append("\n[SQL 결과]")
            for idx, row in enumerate(rows[:30], start=1):
                parts.append(f"{idx}. {row}")

        if vector_result and vector_result.documents:
            parts.append("\n[Vector 검색 결과]")
            for idx, item in enumerate(vector_result.results[:8], start=1):
                metadata = item.document.metadata
                parts.append(
                    "\n".join(
                        [
                            f"문서 {idx}",
                            f"- dept: {metadata.get('dept')}",
                            f"- dept_name: {metadata.get('dept_name')}",
                            f"- content_type: {metadata.get('content_type')}",
                            f"- source_type: {metadata.get('source_type')}",
                            f"- title: {metadata.get('title')}",
                            f"- source: {metadata.get('source') or metadata.get('source_url')}",
                            item.document.page_content[:1500],
                        ]
                    )
                )

        return "\n".join(parts)

    def _fallback_answer(
        self,
        analysis: QueryAnalysis,
        context: Any,
        sql_result: Any | None,
        vector_result: VectorRetrievalResult | None,
    ) -> tuple[str, list[dict[str, Any]], list[str]]:
        rows = self._extract_sql_rows(sql_result)

        if analysis.intent == "requirement_info" and not rows:
            return (
                "제공된 자료에서 해당 졸업/수료/이수/논문 요건에 대한 직접 근거를 찾을 수 없습니다.",
                [],
                [],
            )

        if analysis.intent == "department_homepage_info" and rows:
            lines = ["학과별 홈페이지 URL은 다음과 같습니다."]

            for row in rows:
                dept_name = row.get("dept_name") or row.get("dept")
                homepage_url = row.get("homepage_url")

                if homepage_url:
                    lines.append(f"- {dept_name}: {homepage_url}")

            return "\n".join(lines), [], []

        if rows:
            lines = ["조회된 정형 데이터는 다음과 같습니다."]

            for idx, row in enumerate(rows[:10], start=1):
                lines.append(f"{idx}. {row}")

            return "\n".join(lines), [], []

        if vector_result and vector_result.documents:
            lines = [
                "검색된 문서 근거를 바탕으로 요약하면 다음과 같습니다.",
                "",
            ]

            for idx, item in enumerate(vector_result.results[:3], start=1):
                metadata = item.document.metadata
                title = metadata.get("title") or f"문서 {idx}"
                snippet = item.document.page_content[:500].replace("\n", " ")
                lines.append(f"- {title}: {snippet}...")

            return "\n".join(lines), [], []

        return (
            "제공된 자료에서 질문에 대한 근거를 찾을 수 없습니다. "
            "학과명이나 알고 싶은 정보 유형을 더 구체적으로 입력해주세요.",
            [],
            [],
        )

    # ------------------------------------------------------------
    # result normalize / source merge
    # ------------------------------------------------------------

    def _normalize_answer_result(
        self,
        raw_result: Any,
    ) -> tuple[str, list[dict[str, Any]], list[str]]:
        if isinstance(raw_result, str):
            return raw_result, [], []

        if isinstance(raw_result, dict):
            answer = (
                raw_result.get("answer")
                or raw_result.get("content")
                or raw_result.get("message")
                or ""
            )
            sources = raw_result.get("sources") or []
            warnings = raw_result.get("warnings") or []

            return str(answer), list(sources), list(warnings)

        answer = getattr(raw_result, "answer", None)
        if answer is None:
            answer = getattr(raw_result, "content", None)

        sources = getattr(raw_result, "sources", [])
        warnings = getattr(raw_result, "warnings", [])

        if answer is None:
            answer = str(raw_result)

        return str(answer), list(sources or []), list(warnings or [])

    def _merge_sources(
        self,
        answer_sources: list[dict[str, Any]],
        sql_result: Any | None,
        vector_result: VectorRetrievalResult | None,
        context: Any,
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []

        sources.extend(answer_sources or [])

        # ContextBuilder가 sources를 갖고 있으면 우선 사용
        context_sources = self._extract_context_sources(context)
        sources.extend(context_sources)

        # SQL source
        sql_sources = self._extract_sql_sources(sql_result)
        sources.extend(sql_sources)

        # Vector source
        if vector_result:
            for item in vector_result.results:
                metadata = item.document.metadata
                source_url = metadata.get("source") or metadata.get("source_url") or metadata.get("url") or ""

                sources.append(
                    {
                        "source_type": "vector",
                        "source": source_url,
                        "title": metadata.get("title") or source_url or "Vector document",
                        "department": metadata.get("dept_name") or metadata.get("dept"),
                        "content_type": metadata.get("content_type"),
                        "metadata": dict(metadata),
                        "score": item.score,
                        "rerank_score": item.rerank_score,
                    }
                )

        return self._deduplicate_sources(sources)

    def _extract_context_sources(self, context: Any) -> list[dict[str, Any]]:
        if context is None:
            return []

        if isinstance(context, dict):
            sources = context.get("sources") or []
            return list(sources)

        sources = getattr(context, "sources", None)

        if sources:
            return list(sources)

        return []

    def _extract_sql_sources(self, sql_result: Any | None) -> list[dict[str, Any]]:
        if sql_result is None:
            return []

        table_name = self._get_attr_or_key(sql_result, "table_name")
        rows = self._extract_sql_rows(sql_result)

        sources: list[dict[str, Any]] = []

        for row in rows[:30]:
            if not isinstance(row, dict):
                continue

            source_url = (
                row.get("source_url")
                or row.get("url")
                or row.get("homepage_url")
                or row.get("website")
                or ""
            )

            title = (
                row.get("title")
                or row.get("dept_name")
                or row.get("name")
                or row.get("course_name")
                or row.get("link_name")
                or table_name
                or "SQL source"
            )

            sources.append(
                {
                    "source_type": "sql",
                    "source": source_url,
                    "title": title,
                    "department": row.get("dept_name") or row.get("dept"),
                    "content_type": table_name,
                    "metadata": {
                        "table_name": table_name,
                        **row,
                    },
                }
            )

        if not sources and table_name:
            sources.append(
                {
                    "source_type": "sql",
                    "source": "",
                    "title": str(table_name),
                    "department": "",
                    "content_type": str(table_name),
                    "metadata": {
                        "table_name": table_name,
                        "row_count": len(rows),
                    },
                }
            )

        return sources

    def _deduplicate_sources(
        self,
        sources: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()

        for source in sources:
            key = "|".join(
                [
                    str(source.get("source_type", "")),
                    str(source.get("source", "")),
                    str(source.get("title", "")),
                    str(source.get("department", "")),
                    str(source.get("content_type", "")),
                ]
            )

            if key in seen:
                continue

            seen.add(key)
            deduped.append(source)

        return deduped

    # ------------------------------------------------------------
    # utility
    # ------------------------------------------------------------

    def _extract_sql_rows(self, sql_result: Any | None) -> list[dict[str, Any]]:
        if sql_result is None:
            return []

        if isinstance(sql_result, dict):
            rows = sql_result.get("rows") or sql_result.get("results") or []
            return list(rows)

        rows = getattr(sql_result, "rows", None)

        if rows is None:
            rows = getattr(sql_result, "results", None)

        if rows is None:
            return []

        return list(rows)

    def _is_empty_sql_result(self, sql_result: Any | None) -> bool:
        return len(self._extract_sql_rows(sql_result)) == 0

    def _can_use_vector_fallback_for_sql(self, analysis: QueryAnalysis) -> bool:
        """
        SQL 결과가 비어 있을 때 vector fallback을 사용할 수 있는지 판단.

        requirement_info는 데이터가 없으면 없다고 말해야 하므로 fallback을 남용하지 않는다.
        department_homepage_info도 대표 홈페이지 seed 테이블이 있어야 하므로 fallback 불필요.
        """
        if analysis.intent in {
            "requirement_info",
            "department_homepage_info",
            "kaist_profile_info",
            "kaist_statistics_info",
            "kaist_link_info",
        }:
            return False

        return True

    def _get_attr_or_key(self, obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    def _extract_warnings(self, obj: Any | None) -> list[str]:
        if obj is None:
            return []

        if isinstance(obj, dict):
            warnings = obj.get("warnings") or []
            return [str(warning) for warning in warnings if warning]

        warnings = getattr(obj, "warnings", [])

        return [str(warning) for warning in warnings if warning]

    def _deduplicate_strings(self, values: list[str]) -> list[str]:
        results: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not value or value in seen:
                continue

            seen.add(value)
            results.append(value)

        return results

    def _make_debug_context(
        self,
        analysis: QueryAnalysis,
        sql_result: Any | None,
        vector_result: VectorRetrievalResult | None,
        context: Any,
    ) -> dict[str, Any] | None:
        if not self.include_debug_context:
            return None

        debug: dict[str, Any] = {
            "analysis": analysis.to_dict(),
            "sql_result": self._debug_sql_result(sql_result),
            "vector_result": vector_result.to_debug_dict() if vector_result else None,
            "context_type": type(context).__name__ if context is not None else None,
        }

        return debug

    def _debug_sql_result(self, sql_result: Any | None) -> Any:
        if sql_result is None:
            return None

        if isinstance(sql_result, dict):
            return sql_result

        if hasattr(sql_result, "to_debug_dict"):
            return sql_result.to_debug_dict()

        if hasattr(sql_result, "to_dict"):
            return sql_result.to_dict()

        result = {
            "type": type(sql_result).__name__,
            "table_name": self._get_attr_or_key(sql_result, "table_name"),
            "message": self._get_attr_or_key(sql_result, "message"),
            "rows": self._extract_sql_rows(sql_result)[:5],
            "warnings": self._extract_warnings(sql_result),
        }

        return result

    def _chunk_answer_for_streaming(self, answer: str) -> list[str]:
        if not answer:
            return []

        chunks: list[str] = []
        buffer = ""

        for char in answer:
            buffer += char

            if len(buffer) >= 20 or char in {"\n", ".", "?", "!", "。"}:
                chunks.append(buffer)
                buffer = ""

        if buffer:
            chunks.append(buffer)

        return chunks


# ============================================================
# 3. 기본 pipeline 생성 함수
# ============================================================

def create_default_pipeline(
    include_sql: bool = True,
    include_debug_context: bool = False,
    preload_vector_retriever: bool = True,
    preload_answer_generator: bool = False,
) -> RagPipeline:
    load_dotenv()

    question_analyzer = QuestionAnalyzer()

    sql_retriever = None
    vector_retriever = None
    context_builder = None
    answer_generator = None

    warnings: list[str] = []

    if include_sql and SQLTool is not None:
        try:
            sql_retriever = SQLTool()
        except Exception as exc:
            warnings.append(f"SQLTool 초기화 실패: {type(exc).__name__}: {exc}")

    if preload_vector_retriever:
        try:
            vector_retriever = VectorRetriever(
                question_analyzer=question_analyzer,
            )
        except Exception as exc:
            warnings.append(f"VectorRetriever 초기화 실패: {type(exc).__name__}: {exc}")
            vector_retriever = None

    if ContextBuilder is not None:
        try:
            context_builder = ContextBuilder()
        except Exception as exc:
            warnings.append(f"ContextBuilder 초기화 실패: {type(exc).__name__}: {exc}")
            context_builder = None

    if preload_answer_generator and AnswerGenerator is not None:
        try:
            answer_generator = AnswerGenerator()
        except Exception as exc:
            warnings.append(f"AnswerGenerator 초기화 실패: {type(exc).__name__}: {exc}")
            answer_generator = None
    elif AnswerGenerator is not None:
        try:
            answer_generator = AnswerGenerator()
        except Exception as exc:
            warnings.append(f"AnswerGenerator 초기화 실패: {type(exc).__name__}: {exc}")
            answer_generator = None

    pipeline = RagPipeline(
        question_analyzer=question_analyzer,
        sql_retriever=sql_retriever,
        vector_retriever=vector_retriever,
        context_builder=context_builder,
        answer_generator=answer_generator,
        include_debug_context=include_debug_context,
    )

    if warnings:
        pipeline._startup_warnings = warnings  # type: ignore[attr-defined]

    return pipeline


# ============================================================
# 4. 수동 테스트
# ============================================================

if __name__ == "__main__":
    pipeline = create_default_pipeline(
        include_sql=True,
        include_debug_context=True,
        preload_vector_retriever=True,
        preload_answer_generator=True,
    )

    questions = [
        "AI대학 학과별 홈페이지 URL을 정리해줘.",
        "AI컴퓨팅학과의 연락처가 문서에 나와 있어?",
        "AI미래학과는 어떤 인재를 양성하려고 해?",
        "AI컴퓨팅학과와 AX학과를 비교해줘.",
        "나는 AI 서비스 적용에 관심이 있는데 어떤 학과가 맞아?",
        "AI컴퓨팅학과의 졸업 요건이 문서에 나와 있어?",
    ]

    for question in questions:
        print("=" * 100)
        print("Q:", question)

        result = pipeline.run(question)

        print("route:", result.route)
        print("intent:", result.intent)
        print("department_code:", result.department_code)
        print("department_codes:", result.department_codes)
        print("needs_clarification:", result.needs_clarification)
        print("warnings:", result.warnings)
        print("sources:", len(result.sources))
        print("answer:")
        print(result.answer[:1500])