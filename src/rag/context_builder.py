from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.query_analyzer import QueryAnalysis


# ============================================================
# 1. 설정 / 결과 dataclass
# ============================================================

@dataclass
class ContextBuilderConfig:
    max_total_context_chars: int = 12_000

    max_sql_rows: int = 40
    max_sql_rows_per_dept: int = 8

    max_vector_docs: int = 8
    max_vector_chars_per_doc: int = 1_500

    include_analysis_section: bool = True
    include_sql_section: bool = True
    include_vector_section: bool = True
    include_warning_section: bool = True


@dataclass
class SourceItem:
    source_type: str
    title: str
    source: str = ""
    department: str | None = None
    content_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BuiltContext:
    question: str
    context_text: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    sql_row_count: int = 0
    vector_doc_count: int = 0
    has_direct_evidence: bool = False

    sql_table_name: str | None = None
    vector_content_types: list[str] = field(default_factory=list)
    vector_departments: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return self.context_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "context_text": self.context_text,
            "sources": self.sources,
            "warnings": self.warnings,
            "sql_row_count": self.sql_row_count,
            "vector_doc_count": self.vector_doc_count,
            "has_direct_evidence": self.has_direct_evidence,
            "sql_table_name": self.sql_table_name,
            "vector_content_types": self.vector_content_types,
            "vector_departments": self.vector_departments,
        }


# ============================================================
# 2. ContextBuilder
# ============================================================

class ContextBuilder:
    def __init__(
        self,
        config: ContextBuilderConfig | None = None,
    ) -> None:
        self.config = config or ContextBuilderConfig()

    # ------------------------------------------------------------
    # public API
    # ------------------------------------------------------------

    def build(
        self,
        question: str | None = None,
        analysis: QueryAnalysis | None = None,
        sql_result: Any | None = None,
        vector_result: Any | None = None,
        **kwargs: Any,
    ) -> BuiltContext:
        if question is None:
            question = ""

            if analysis is not None:
                question = analysis.original_question

        if analysis is None:
            raise ValueError("ContextBuilder.build에는 analysis가 필요합니다.")

        sql_rows = self._extract_sql_rows(sql_result)
        sql_table_name = self._get_attr_or_key(sql_result, "table_name")

        vector_items = self._extract_vector_items(vector_result)

        selected_sql_rows = self._select_sql_rows(
            rows=sql_rows,
            analysis=analysis,
        )

        selected_vector_items = self._select_vector_items(
            vector_items=vector_items,
            analysis=analysis,
        )

        warnings = self._build_warnings(
            analysis=analysis,
            sql_result=sql_result,
            vector_result=vector_result,
            sql_rows=sql_rows,
            vector_items=vector_items,
        )

        sources = self._build_sources(
            sql_rows=selected_sql_rows,
            sql_table_name=sql_table_name,
            vector_items=selected_vector_items,
        )

        has_direct_evidence = self._has_direct_evidence(
            analysis=analysis,
            sql_rows=sql_rows,
            vector_items=vector_items,
        )

        sections: list[str] = []

        if self.config.include_warning_section and warnings:
            sections.append(self._format_warning_section(warnings))

        if self.config.include_analysis_section:
            sections.append(
                self._format_analysis_section(
                    question=question,
                    analysis=analysis,
                    has_direct_evidence=has_direct_evidence,
                )
            )

        if self.config.include_sql_section:
            sql_section = self._format_sql_section(
                rows=selected_sql_rows,
                table_name=sql_table_name,
                total_row_count=len(sql_rows),
            )

            if sql_section:
                sections.append(sql_section)

        if self.config.include_vector_section:
            vector_section = self._format_vector_section(
                vector_items=selected_vector_items,
                total_doc_count=len(vector_items),
            )

            if vector_section:
                sections.append(vector_section)

        if not selected_sql_rows and not selected_vector_items:
            sections.append(
                "[검색 결과 없음]\n"
                "제공된 SQL/Vector 검색 결과에서 질문에 대한 직접 근거를 찾지 못했습니다."
            )

        context_text = "\n\n".join(sections)
        context_text = self._truncate_context(context_text)

        vector_content_types = self._unique_non_empty(
            [
                str(self._get_vector_metadata(item).get("content_type", ""))
                for item in vector_items
            ]
        )

        vector_departments = self._unique_non_empty(
            [
                str(
                    self._get_vector_metadata(item).get("dept_name")
                    or self._get_vector_metadata(item).get("dept")
                    or ""
                )
                for item in vector_items
            ]
        )

        return BuiltContext(
            question=question,
            context_text=context_text,
            sources=sources,
            warnings=warnings,
            sql_row_count=len(sql_rows),
            vector_doc_count=len(vector_items),
            has_direct_evidence=has_direct_evidence,
            sql_table_name=sql_table_name,
            vector_content_types=vector_content_types,
            vector_departments=vector_departments,
        )

    def build_context(
        self,
        question: str | None = None,
        analysis: QueryAnalysis | None = None,
        sql_result: Any | None = None,
        vector_result: Any | None = None,
        **kwargs: Any,
    ) -> BuiltContext:
        return self.build(
            question=question,
            analysis=analysis,
            sql_result=sql_result,
            vector_result=vector_result,
            **kwargs,
        )

    # ------------------------------------------------------------
    # extraction
    # ------------------------------------------------------------

    def _extract_sql_rows(self, sql_result: Any | None) -> list[dict[str, Any]]:
        if sql_result is None:
            return []

        if isinstance(sql_result, dict):
            rows = sql_result.get("rows") or sql_result.get("results") or []
            return [dict(row) for row in rows if isinstance(row, dict)]

        rows = getattr(sql_result, "rows", None)

        if rows is None:
            rows = getattr(sql_result, "results", None)

        if rows is None:
            return []

        return [dict(row) for row in rows if isinstance(row, dict)]

    def _extract_vector_items(self, vector_result: Any | None) -> list[Any]:
        if vector_result is None:
            return []

        results = getattr(vector_result, "results", None)

        if results is not None:
            return list(results)

        documents = getattr(vector_result, "documents", None)

        if documents is not None:
            return list(documents)

        if isinstance(vector_result, dict):
            results = vector_result.get("results") or vector_result.get("documents") or []
            return list(results)

        return []

    def _get_attr_or_key(
        self,
        obj: Any,
        key: str,
        default: Any = None,
    ) -> Any:
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    def _get_vector_document(self, item: Any) -> Any:
        if hasattr(item, "document"):
            return item.document

        return item

    def _get_vector_metadata(self, item: Any) -> dict[str, Any]:
        document = self._get_vector_document(item)
        metadata = getattr(document, "metadata", None)

        if isinstance(metadata, dict):
            return metadata

        if isinstance(item, dict):
            metadata = item.get("metadata")

            if isinstance(metadata, dict):
                return metadata

        return {}

    def _get_vector_page_content(self, item: Any) -> str:
        document = self._get_vector_document(item)
        content = getattr(document, "page_content", None)

        if content is not None:
            return str(content)

        if isinstance(item, dict):
            return str(item.get("page_content") or item.get("text") or "")

        return str(document)

    def _get_vector_score(self, item: Any) -> Any:
        if hasattr(item, "score"):
            return item.score

        if isinstance(item, dict):
            return item.get("score")

        return None

    def _get_vector_stage(self, item: Any) -> str | None:
        if hasattr(item, "search_stage"):
            return item.search_stage

        if isinstance(item, dict):
            return item.get("search_stage")

        return None

    # ------------------------------------------------------------
    # row selection
    # ------------------------------------------------------------

    def _select_sql_rows(
        self,
        rows: list[dict[str, Any]],
        analysis: QueryAnalysis,
    ) -> list[dict[str, Any]]:
        if not rows:
            return []

        if len(rows) <= self.config.max_sql_rows:
            return rows

        if analysis.department_code:
            dept_rows = [
                row for row in rows
                if row.get("dept") == analysis.department_code
            ]

            if dept_rows:
                return dept_rows[: self.config.max_sql_rows]

        return self._balanced_sample_rows_by_department(
            rows=rows,
            max_total_rows=self.config.max_sql_rows,
            max_rows_per_dept=self.config.max_sql_rows_per_dept,
        )

    def _balanced_sample_rows_by_department(
        self,
        rows: list[dict[str, Any]],
        max_total_rows: int,
        max_rows_per_dept: int,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}

        for row in rows:
            dept_key = str(
                row.get("dept")
                or row.get("dept_name")
                or row.get("department")
                or "unknown"
            )

            grouped.setdefault(dept_key, []).append(row)

        selected: list[dict[str, Any]] = []

        preferred_order = ["aic", "ai_systems", "ax", "fx"]

        ordered_keys = [
            key for key in preferred_order
            if key in grouped
        ] + [
            key for key in grouped
            if key not in preferred_order
        ]

        for key in ordered_keys:
            selected.extend(grouped[key][:max_rows_per_dept])

            if len(selected) >= max_total_rows:
                break

        return selected[:max_total_rows]

    def _select_vector_items(
        self,
        vector_items: list[Any],
        analysis: QueryAnalysis,
    ) -> list[Any]:
        if not vector_items:
            return []

        if analysis.intent in {"comparison_info", "recommendation_info"}:
            dept_codes = analysis.department_codes or ["aic", "ai_systems", "ax", "fx"]

            return self._balanced_sample_vector_by_department(
                vector_items=vector_items,
                dept_codes=dept_codes,
                max_docs=self.config.max_vector_docs,
            )

        return vector_items[: self.config.max_vector_docs]

    def _balanced_sample_vector_by_department(
        self,
        vector_items: list[Any],
        dept_codes: list[str],
        max_docs: int,
    ) -> list[Any]:
        selected: list[Any] = []
        used_ids: set[str] = set()

        for dept_code in dept_codes:
            dept_items = [
                item for item in vector_items
                if self._get_vector_metadata(item).get("dept") == dept_code
            ]

            for item in dept_items:
                item_id = self._make_vector_item_id(item)

                if item_id in used_ids:
                    continue

                selected.append(item)
                used_ids.add(item_id)

                if len(selected) >= max_docs:
                    return selected

                break

        for item in vector_items:
            item_id = self._make_vector_item_id(item)

            if item_id in used_ids:
                continue

            selected.append(item)
            used_ids.add(item_id)

            if len(selected) >= max_docs:
                break

        return selected

    def _make_vector_item_id(self, item: Any) -> str:
        metadata = self._get_vector_metadata(item)

        return "|".join(
            [
                str(metadata.get("content_hash", "")),
                str(metadata.get("source_type", "")),
                str(metadata.get("dept", "")),
                str(metadata.get("title", "")),
                self._get_vector_page_content(item)[:200],
            ]
        )

    # ------------------------------------------------------------
    # warnings / evidence
    # ------------------------------------------------------------

    def _build_warnings(
        self,
        analysis: QueryAnalysis,
        sql_result: Any | None,
        vector_result: Any | None,
        sql_rows: list[dict[str, Any]],
        vector_items: list[Any],
    ) -> list[str]:
        warnings: list[str] = []

        warnings.extend(self._extract_warnings(sql_result))
        warnings.extend(self._extract_warnings(vector_result))

        if analysis.intent == "requirement_info" and not sql_rows:
            warnings.append(
                "현재 SQL 데이터에는 졸업/수료/이수/논문 요건에 대한 직접 근거가 없습니다."
            )

        if analysis.intent == "department_homepage_info" and not sql_rows:
            warnings.append(
                "department_homepage 테이블에서 학과별 대표 홈페이지 정보를 찾지 못했습니다."
            )

        if analysis.intent == "course_info":
            if analysis.department_code == "ai_systems" and not sql_rows and not vector_items:
                warnings.append(
                    "현재 데이터에는 AI시스템학과 교과목 정보가 부족합니다."
                )

        if vector_result is not None:
            used_fallback = self._get_attr_or_key(vector_result, "used_fallback", False)

            if used_fallback:
                warnings.append(
                    "Vector 검색에서 fallback 결과가 포함되었습니다. "
                    "fallback 문서는 질문의 직접 근거인지 주의해서 사용해야 합니다."
                )

        return self._unique_non_empty([str(w) for w in warnings if w])

    def _extract_warnings(self, obj: Any | None) -> list[str]:
        if obj is None:
            return []

        if isinstance(obj, dict):
            warnings = obj.get("warnings") or []
            return [str(w) for w in warnings if w]

        warnings = getattr(obj, "warnings", [])

        return [str(w) for w in warnings if w]

    def _has_direct_evidence(
        self,
        analysis: QueryAnalysis,
        sql_rows: list[dict[str, Any]],
        vector_items: list[Any],
    ) -> bool:
        if analysis.intent in {
            "course_info",
            "person_info",
            "office_contact_info",
            "asset_or_link_info",
            "department_homepage_info",
            "requirement_info",
            "kaist_profile_info",
            "kaist_statistics_info",
            "kaist_link_info",
        }:
            return len(sql_rows) > 0

        if analysis.intent in {"admission_info", "event_info"}:
            return len(sql_rows) > 0 or len(vector_items) > 0

        if analysis.intent == "comparison_info":
            if not vector_items:
                return False

            target_depts = analysis.department_codes or []

            if not target_depts:
                return len(vector_items) > 0

            found_depts = {
                self._get_vector_metadata(item).get("dept")
                for item in vector_items
            }

            return all(dept in found_depts for dept in target_depts)

        if analysis.intent == "recommendation_info":
            if not vector_items:
                return False

            found_depts = {
                self._get_vector_metadata(item).get("dept")
                for item in vector_items
                if self._get_vector_metadata(item).get("dept")
            }

            return len(found_depts) >= 2

        if analysis.intent == "department_overview":
            if not vector_items:
                return False

            if analysis.department_code:
                return any(
                    self._get_vector_metadata(item).get("dept") == analysis.department_code
                    for item in vector_items
                )

            return len(vector_items) > 0

        return bool(sql_rows or vector_items)

    # ------------------------------------------------------------
    # formatting
    # ------------------------------------------------------------

    def _format_warning_section(self, warnings: list[str]) -> str:
        lines = ["[주의 / 검색 상태]"]

        for warning in warnings:
            lines.append(f"- {warning}")

        return "\n".join(lines)

    def _format_analysis_section(
        self,
        question: str,
        analysis: QueryAnalysis,
        has_direct_evidence: bool,
    ) -> str:
        lines = [
            "[질문 분석]",
            f"원 질문: {question}",
            f"정규화 질문: {analysis.normalized_question}",
            f"route: {analysis.route}",
            f"intent: {analysis.intent}",
            f"intent 설명: {analysis.intent_description}",
            f"content_type: {analysis.content_type}",
            f"department_code: {analysis.department_code}",
            f"department_name: {analysis.department_name}",
            f"department_codes: {analysis.department_codes}",
            f"department_names: {analysis.department_names}",
            f"has_direct_evidence: {has_direct_evidence}",
        ]

        if analysis.rewritten_question:
            lines.append(f"검색용 질문: {analysis.rewritten_question}")

        return "\n".join(lines)

    def _format_sql_section(
        self,
        rows: list[dict[str, Any]],
        table_name: str | None,
        total_row_count: int,
    ) -> str:
        if not rows:
            return ""

        lines = [
            "[SQL 정형 데이터 근거]",
            f"table: {table_name or 'unknown'}",
            f"selected_rows: {len(rows)} / total_rows: {total_row_count}",
        ]

        for idx, row in enumerate(rows, start=1):
            lines.append(f"\nSQL_ROW_{idx}")
            lines.append(self._format_sql_row(row))

        return "\n".join(lines)

    def _format_sql_row(self, row: dict[str, Any]) -> str:
        priority_keys = [
            "source_table",
            "dept",
            "dept_name",
            "name",
            "name_ko",
            "name_en",
            "role",
            "role_normalized",
            "email",
            "phone",
            "office",
            "homepage",
            "program_name",
            "website",
            "building_location",
            "course_code",
            "course_name",
            "course_type",
            "credit",
            "course_description",
            "admission_type",
            "admission_type_norm",
            "title",
            "content",
            "schedule_date",
            "min_gpa",
            "event_date",
            "summary",
            "homepage_url",
            "admission_url",
            "faculty_url",
            "curriculum_url",
            "item",
            "value_raw",
            "value_number",
            "url",
            "source_url",
            "source",
            "contact_text",
        ]

        lines: list[str] = []
        used_keys: set[str] = set()

        for key in priority_keys:
            value = row.get(key)

            if self._is_empty(value):
                continue

            lines.append(f"- {key}: {value}")
            used_keys.add(key)

        for key, value in row.items():
            if key in used_keys:
                continue

            if self._is_empty(value):
                continue

            if key.endswith("_id") or key in {"missing_fields", "crawled_at", "source_sheet"}:
                continue

            lines.append(f"- {key}: {value}")

            if len(lines) >= 25:
                break

        return "\n".join(lines)

    def _format_vector_section(
        self,
        vector_items: list[Any],
        total_doc_count: int,
    ) -> str:
        if not vector_items:
            return ""

        lines = [
            "[Vector 문서 근거]",
            f"selected_docs: {len(vector_items)} / total_docs: {total_doc_count}",
        ]

        for idx, item in enumerate(vector_items, start=1):
            metadata = self._get_vector_metadata(item)
            content = self._get_vector_page_content(item)
            score = self._get_vector_score(item)
            stage = self._get_vector_stage(item)

            content = content[: self.config.max_vector_chars_per_doc]

            lines.append(f"\nVECTOR_DOC_{idx}")
            lines.append(f"- search_stage: {stage}")
            lines.append(f"- score: {score}")
            lines.append(f"- dept: {metadata.get('dept')}")
            lines.append(f"- dept_name: {metadata.get('dept_name')}")
            lines.append(f"- source_type: {metadata.get('source_type')}")
            lines.append(f"- content_type: {metadata.get('content_type')}")
            lines.append(f"- title: {metadata.get('title')}")
            lines.append(f"- source: {metadata.get('source') or metadata.get('source_url') or metadata.get('url')}")
            lines.append("[content]")
            lines.append(content)

        return "\n".join(lines)

    # ------------------------------------------------------------
    # sources
    # ------------------------------------------------------------

    def _build_sources(
        self,
        sql_rows: list[dict[str, Any]],
        sql_table_name: str | None,
        vector_items: list[Any],
    ) -> list[dict[str, Any]]:
        sources: list[SourceItem] = []

        for row in sql_rows:
            sources.append(
                SourceItem(
                    source_type="sql",
                    title=self._make_sql_source_title(row, sql_table_name),
                    source=self._make_sql_source_url(row),
                    department=row.get("dept_name") or row.get("dept"),
                    content_type=sql_table_name,
                    metadata={
                        "table_name": sql_table_name,
                        **row,
                    },
                )
            )

        for item in vector_items:
            metadata = self._get_vector_metadata(item)

            sources.append(
                SourceItem(
                    source_type="vector",
                    title=str(metadata.get("title") or "Vector document"),
                    source=str(
                        metadata.get("source")
                        or metadata.get("source_url")
                        or metadata.get("url")
                        or ""
                    ),
                    department=metadata.get("dept_name") or metadata.get("dept"),
                    content_type=metadata.get("content_type"),
                    metadata=dict(metadata),
                )
            )

        return self._deduplicate_sources([source.to_dict() for source in sources])

    def _make_sql_source_title(
        self,
        row: dict[str, Any],
        table_name: str | None,
    ) -> str:
        for key in [
            "title",
            "dept_name",
            "name",
            "course_name",
            "program_name",
            "link_name",
            "item",
            "homepage_url",
            "url",
        ]:
            value = row.get(key)

            if not self._is_empty(value):
                return str(value)

        return str(table_name or "SQL source")

    def _make_sql_source_url(self, row: dict[str, Any]) -> str:
        for key in [
            "source_url",
            "homepage_url",
            "url",
            "website",
            "homepage",
            "admission_url",
            "faculty_url",
            "curriculum_url",
        ]:
            value = row.get(key)

            if not self._is_empty(value):
                return str(value)

        return ""

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
                    str(source.get("title", "")),
                    str(source.get("source", "")),
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
    # misc
    # ------------------------------------------------------------

    def _truncate_context(self, context_text: str) -> str:
        if len(context_text) <= self.config.max_total_context_chars:
            return context_text

        truncated = context_text[: self.config.max_total_context_chars]

        return (
            truncated
            + "\n\n[TRUNCATED]\n"
            + "context가 길어 일부 내용이 잘렸습니다. 답변은 남아 있는 근거 안에서만 작성해야 합니다."
        )

    def _unique_non_empty(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            value = str(value).strip()

            if not value:
                continue

            if value in {"None", "nan", "NaN"}:
                continue

            if value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result

    def _is_empty(self, value: Any) -> bool:
        if value is None:
            return True

        text = str(value).strip()

        return text == "" or text.lower() in {"none", "nan", "null", "n/a", "na"}


# ============================================================
# 3. 수동 테스트
# ============================================================

if __name__ == "__main__":
    from src.rag.query_analyzer import QuestionAnalyzer

    analyzer = QuestionAnalyzer()
    analysis = analyzer.analyze("AI대학 학과별 홈페이지 URL을 정리해줘.")

    mock_sql_result = {
        "table_name": "department_homepage",
        "rows": [
            {
                "dept": "aic",
                "dept_name": "AI컴퓨팅학과",
                "homepage_url": "https://aic.kaist.ac.kr/",
                "source": "manual_seed",
            },
            {
                "dept": "ai_systems",
                "dept_name": "AI시스템학과",
                "homepage_url": "https://ai-systems.kaist.ac.kr/",
                "source": "manual_seed",
            },
        ],
        "warnings": [],
    }

    builder = ContextBuilder()
    built_context = builder.build(
        question="AI대학 학과별 홈페이지 URL을 정리해줘.",
        analysis=analysis,
        sql_result=mock_sql_result,
        vector_result=None,
    )

    print(built_context.context_text)
    print("\n[SOURCES]")
    print(json.dumps(built_context.sources, ensure_ascii=False, indent=2))