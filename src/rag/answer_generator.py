from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.query_analyzer import QueryAnalysis


# ============================================================
# 1. 설정 / 결과 dataclass
# ============================================================

@dataclass
class AnswerGeneratorConfig:
    model_name: str = "gpt-4.1-mini"
    temperature: float = 0.0
    max_retries: int = 2
    request_timeout: int = 60

    # context가 길어도 AnswerGenerator에서는 한 번 더 방어적으로 제한
    max_context_chars: int = 12_000

    # LLM을 쓰지 않고 deterministic 답변할 intent
    deterministic_intents: set[str] = field(
        default_factory=lambda: {
            "department_homepage_info",
            "requirement_info",
        }
    )


@dataclass
class GeneratedAnswer:
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# 2. AnswerGenerator
# ============================================================

class AnswerGenerator:
    def __init__(
        self,
        config: AnswerGeneratorConfig | None = None,
    ) -> None:
        load_dotenv()
        self.config = config or AnswerGeneratorConfig()

    # ------------------------------------------------------------
    # public API
    # ------------------------------------------------------------

    def generate(
        self,
        question: str,
        context: Any,
        analysis: QueryAnalysis,
        sql_result: Any | None = None,
        vector_result: Any | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        RagPipeline에서 호출하는 기본 답변 생성 함수.

        반환 형식:
            {
                "answer": "...",
                "sources": [...],
                "warnings": [...]
            }
        """
        normalized_context = self._normalize_context(context)
        context_text = normalized_context["context_text"]
        context_sources = normalized_context["sources"]
        context_warnings = normalized_context["warnings"]
        has_direct_evidence = normalized_context["has_direct_evidence"]

        sql_rows = self._extract_sql_rows(sql_result)
        vector_docs = self._extract_vector_docs(vector_result)

        warnings: list[str] = []
        warnings.extend(context_warnings)
        warnings.extend(self._extract_warnings(sql_result))
        warnings.extend(self._extract_warnings(vector_result))

        # 1. clarify route는 그대로 안내
        if analysis.route == "clarify":
            answer = analysis.clarifying_message or "질문을 조금 더 구체적으로 입력해주세요."

            return GeneratedAnswer(
                answer=answer,
                sources=[],
                warnings=self._deduplicate_strings(warnings),
            ).to_dict()

        # 2. 학과별 홈페이지 URL은 SQL row 기반으로 확정 답변
        if analysis.intent == "department_homepage_info":
            return self._answer_department_homepage(
                sql_rows=sql_rows,
                sources=context_sources,
                warnings=warnings,
            ).to_dict()

        # 3. 졸업/수료/이수/논문 요건은 데이터 없으면 명확히 근거 없음
        if analysis.intent == "requirement_info":
            return self._answer_requirement(
                analysis=analysis,
                sql_rows=sql_rows,
                sources=context_sources,
                warnings=warnings,
            ).to_dict()

        # 4. 직접 근거가 없으면 LLM 호출 금지
        if not self._has_enough_direct_evidence(
            analysis=analysis,
            has_direct_evidence=has_direct_evidence,
            sql_rows=sql_rows,
            vector_docs=vector_docs,
        ):
            return self._answer_no_direct_evidence(
                analysis=analysis,
                sql_rows=sql_rows,
                vector_docs=vector_docs,
                warnings=warnings,
            ).to_dict()

        # 5. SQL 정형 답변 중 간단한 것은 deterministic 처리
        deterministic_answer = self._try_deterministic_answer(
            analysis=analysis,
            sql_rows=sql_rows,
            context_sources=context_sources,
            warnings=warnings,
        )

        if deterministic_answer is not None:
            return deterministic_answer.to_dict()

        # 6. 근거가 있을 때만 LLM 답변 생성
        answer_text, llm_warnings = self._generate_with_llm(
            question=question,
            analysis=analysis,
            context_text=context_text,
        )

        warnings.extend(llm_warnings)

        return GeneratedAnswer(
            answer=answer_text,
            sources=context_sources,
            warnings=self._deduplicate_strings(warnings),
        ).to_dict()

    def answer(
        self,
        question: str,
        context: Any,
        analysis: QueryAnalysis,
        sql_result: Any | None = None,
        vector_result: Any | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.generate(
            question=question,
            context=context,
            analysis=analysis,
            sql_result=sql_result,
            vector_result=vector_result,
            **kwargs,
        )

    def __call__(
        self,
        question: str,
        context: Any,
        analysis: QueryAnalysis,
        sql_result: Any | None = None,
        vector_result: Any | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.generate(
            question=question,
            context=context,
            analysis=analysis,
            sql_result=sql_result,
            vector_result=vector_result,
            **kwargs,
        )

    # ------------------------------------------------------------
    # deterministic answers
    # ------------------------------------------------------------

    def _answer_department_homepage(
        self,
        sql_rows: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        warnings: list[str],
    ) -> GeneratedAnswer:
        if not sql_rows:
            return GeneratedAnswer(
                answer=(
                    "제공된 자료에서 학과별 대표 홈페이지 URL 정보를 찾을 수 없습니다. "
                    "`department_homepage` 테이블 적재 여부를 확인해야 합니다."
                ),
                sources=[],
                warnings=self._deduplicate_strings(warnings),
            )

        lines = ["학과별 대표 홈페이지 URL은 다음과 같습니다."]

        preferred_order = ["aic", "ai_systems", "ax", "fx"]
        rows = sorted(
            sql_rows,
            key=lambda row: preferred_order.index(row.get("dept"))
            if row.get("dept") in preferred_order
            else 999,
        )

        for row in rows:
            dept_name = row.get("dept_name") or row.get("dept") or "학과명 미상"
            homepage_url = row.get("homepage_url")

            if homepage_url:
                lines.append(f"- {dept_name}: {homepage_url}")
            else:
                lines.append(f"- {dept_name}: 홈페이지 URL이 제공된 자료에 없습니다.")

        return GeneratedAnswer(
            answer="\n".join(lines),
            sources=sources,
            warnings=self._deduplicate_strings(warnings),
        )

    def _answer_requirement(
        self,
        analysis: QueryAnalysis,
        sql_rows: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        warnings: list[str],
    ) -> GeneratedAnswer:
        if not sql_rows:
            dept_text = ""

            if analysis.department_name:
                dept_text = f"{analysis.department_name}의 "
            elif analysis.department_names:
                dept_text = f"{', '.join(analysis.department_names)}의 "
            else:
                dept_text = "AI대학 학과별 "

            return GeneratedAnswer(
                answer=(
                    f"제공된 자료에서 {dept_text}졸업/수료/이수/논문 요건에 대한 "
                    "직접 근거를 찾을 수 없습니다. 현재 데이터에는 입학 정보와 교과목 정보는 있으나, "
                    "졸업요건·수료요건·논문 제출요건을 확인할 수 있는 정형 데이터가 부족합니다."
                ),
                sources=[],
                warnings=self._deduplicate_strings(
                    warnings
                    + [
                        "department_requirement 테이블에 조회된 row가 없습니다.",
                    ]
                ),
            )

        lines = ["제공된 자료에서 확인되는 요건 정보는 다음과 같습니다."]

        for idx, row in enumerate(sql_rows, start=1):
            dept_name = row.get("dept_name") or row.get("dept") or "학과명 미상"
            program = row.get("program") or "과정 미상"
            requirement_type = row.get("requirement_type") or "요건 유형 미상"
            requirement_name = row.get("requirement_name") or "요건명 미상"
            description = row.get("description") or ""
            credits = row.get("credits") or ""

            line = f"{idx}. {dept_name} / {program} / {requirement_type} / {requirement_name}"

            if credits:
                line += f" / 학점: {credits}"

            if description:
                line += f"\n   - {description}"

            lines.append(line)

        return GeneratedAnswer(
            answer="\n".join(lines),
            sources=sources,
            warnings=self._deduplicate_strings(warnings),
        )

    def _try_deterministic_answer(
        self,
        analysis: QueryAnalysis,
        sql_rows: list[dict[str, Any]],
        context_sources: list[dict[str, Any]],
        warnings: list[str],
    ) -> GeneratedAnswer | None:
        if not sql_rows:
            return None

        if analysis.intent == "kaist_profile_info":
            return self._answer_simple_sql_rows(
                intro="KAIST 기본 정보는 다음과 같습니다.",
                sql_rows=sql_rows,
                sources=context_sources,
                warnings=warnings,
                keys=["item", "content", "note", "source_url"],
            )

        if analysis.intent == "kaist_statistics_info":
            return self._answer_simple_sql_rows(
                intro="KAIST 통계 정보는 다음과 같습니다.",
                sql_rows=sql_rows,
                sources=context_sources,
                warnings=warnings,
                keys=["stat_group", "level", "value_raw", "value_number", "note"],
            )

        if analysis.intent == "kaist_link_info":
            return self._answer_simple_sql_rows(
                intro="KAIST 공식 링크 정보는 다음과 같습니다.",
                sql_rows=sql_rows,
                sources=context_sources,
                warnings=warnings,
                keys=["link_name", "url", "note"],
            )

        return None

    def _answer_simple_sql_rows(
        self,
        intro: str,
        sql_rows: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        warnings: list[str],
        keys: list[str],
    ) -> GeneratedAnswer:
        lines = [intro]

        for idx, row in enumerate(sql_rows[:20], start=1):
            parts = []

            for key in keys:
                value = row.get(key)

                if self._is_empty(value):
                    continue

                parts.append(f"{key}: {value}")

            if parts:
                lines.append(f"{idx}. " + " / ".join(parts))

        return GeneratedAnswer(
            answer="\n".join(lines),
            sources=sources,
            warnings=self._deduplicate_strings(warnings),
        )

    def _answer_no_direct_evidence(
        self,
        analysis: QueryAnalysis,
        sql_rows: list[dict[str, Any]],
        vector_docs: list[Any],
        warnings: list[str],
    ) -> GeneratedAnswer:
        if analysis.intent == "course_info" and analysis.department_code == "ai_systems":
            answer = (
                "제공된 자료에서 AI시스템학과의 교육과정 또는 교과목에 대한 직접 근거를 찾을 수 없습니다. "
                "현재 보유 데이터에는 AI시스템학과 입학/교수진 자료는 있으나, 교과목 데이터가 부족합니다."
            )
        elif analysis.intent == "person_info":
            answer = (
                "제공된 자료에서 질문에 맞는 교수진 정보를 찾을 수 없습니다. "
                "교수명, 학과명, 이메일, 연구분야 중 어떤 정보를 원하는지 더 구체화해야 합니다."
            )
        elif analysis.intent == "office_contact_info":
            answer = (
                "제공된 자료에서 해당 학과의 연락처에 대한 직접 근거를 찾을 수 없습니다. "
                "학과 사무실, 이메일, 전화번호 데이터 적재 여부를 확인해야 합니다."
            )
        elif analysis.intent == "comparison_info":
            answer = (
                "비교 대상 학과를 모두 설명할 수 있는 직접 근거가 부족합니다. "
                "검색 결과가 한쪽 학과에 치우쳤거나 학과 소개 자료가 vectorstore에 충분히 들어가지 않았을 수 있습니다."
            )
        elif analysis.intent == "recommendation_info":
            answer = (
                "관심사 기반 학과 추천에 필요한 직접 근거가 부족합니다. "
                "학과별 교육 방향, 핵심 키워드, 추천 대상 정보를 담은 department profile 데이터가 필요합니다."
            )
        elif analysis.intent == "department_overview":
            dept_text = analysis.department_name or "해당 학과"
            answer = (
                f"제공된 자료에서 {dept_text} 소개에 대한 직접 근거를 찾을 수 없습니다. "
                "학과 소개 PDF 또는 웹페이지 본문이 vectorstore에 제대로 포함되었는지 확인해야 합니다."
            )
        else:
            answer = (
                "제공된 자료에서 질문에 대한 직접 근거를 찾을 수 없습니다. "
                "데이터가 부족하거나 검색 라우팅이 적절하지 않을 수 있습니다."
            )

        return GeneratedAnswer(
            answer=answer,
            sources=[],
            warnings=self._deduplicate_strings(warnings),
        )

    # ------------------------------------------------------------
    # LLM generation
    # ------------------------------------------------------------

    def _generate_with_llm(
        self,
        question: str,
        analysis: QueryAnalysis,
        context_text: str,
    ) -> tuple[str, list[str]]:
        warnings: list[str] = []

        if not os.getenv("OPENAI_API_KEY"):
            return (
                "OPENAI_API_KEY가 설정되어 있지 않아 LLM 답변을 생성할 수 없습니다.",
                ["OPENAI_API_KEY가 설정되어 있지 않습니다."],
            )

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_openai import ChatOpenAI
        except ModuleNotFoundError as exc:
            return (
                "LLM 답변 생성에 필요한 패키지가 설치되어 있지 않습니다.",
                [f"ModuleNotFoundError: {exc}"],
            )

        llm = ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.temperature,
            request_timeout=self.config.request_timeout,
            max_retries=self.config.max_retries,
        )

        context_text = context_text[: self.config.max_context_chars]

        system_prompt = self._build_system_prompt()
        human_prompt = self._build_human_prompt(
            question=question,
            analysis=analysis,
            context_text=context_text,
        )

        try:
            response = llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt),
                ]
            )

            answer = str(response.content).strip()

            if not answer:
                return (
                    "답변 생성 결과가 비어 있습니다.",
                    ["LLM response content is empty."],
                )

            return answer, warnings

        except Exception as exc:
            return (
                "LLM 답변 생성 중 오류가 발생했습니다.",
                [f"{type(exc).__name__}: {exc}"],
            )

    def _build_system_prompt(self) -> str:
        return """
당신은 KAIST AI College 학과 정보 안내 챗봇입니다.

반드시 지켜야 할 규칙:
1. 제공된 context 안의 근거만 사용하세요.
2. context에 없는 내용은 추측하지 마세요.
3. 근거가 부족하면 "제공된 자료에서 확인할 수 없습니다"라고 말하세요.
4. SQL 정형 데이터는 사실값으로 우선 사용하세요.
5. Vector 문서는 설명 근거로 사용하세요.
6. fallback 문서나 warning이 있으면 단정하지 말고 제한을 함께 말하세요.
7. 졸업요건, 수료요건, 논문요건, 경쟁률, 등록금, 취업률, 합격 가능성은 직접 근거가 없으면 절대 답하지 마세요.
8. 답변은 한국어로 작성하세요.
9. 가능하면 표나 항목화된 구조로 간결하게 정리하세요.
10. 마지막에 "근거" 항목을 짧게 포함하세요.
""".strip()

    def _build_human_prompt(
        self,
        question: str,
        analysis: QueryAnalysis,
        context_text: str,
    ) -> str:
        return f"""
[사용자 질문]
{question}

[질문 분석]
- route: {analysis.route}
- intent: {analysis.intent}
- department_code: {analysis.department_code}
- department_codes: {analysis.department_codes}
- content_type: {analysis.content_type}

[제공된 context]
{context_text}

위 context만 근거로 답변하세요.
""".strip()

    # ------------------------------------------------------------
    # context normalize
    # ------------------------------------------------------------

    def _normalize_context(self, context: Any) -> dict[str, Any]:
        context_text = ""
        sources: list[dict[str, Any]] = []
        warnings: list[str] = []
        has_direct_evidence = False

        if context is None:
            return {
                "context_text": "",
                "sources": [],
                "warnings": [],
                "has_direct_evidence": False,
            }

        if isinstance(context, str):
            return {
                "context_text": context,
                "sources": [],
                "warnings": [],
                "has_direct_evidence": bool(context.strip()),
            }

        if isinstance(context, dict):
            context_text = str(
                context.get("context_text")
                or context.get("context")
                or context.get("text")
                or ""
            )
            sources = list(context.get("sources") or [])
            warnings = list(context.get("warnings") or [])
            has_direct_evidence = bool(context.get("has_direct_evidence", False))

            return {
                "context_text": context_text,
                "sources": sources,
                "warnings": warnings,
                "has_direct_evidence": has_direct_evidence,
            }

        context_text = str(
            getattr(context, "context_text", None)
            or getattr(context, "context", None)
            or context
        )
        sources = list(getattr(context, "sources", []) or [])
        warnings = list(getattr(context, "warnings", []) or [])
        has_direct_evidence = bool(getattr(context, "has_direct_evidence", False))

        return {
            "context_text": context_text,
            "sources": sources,
            "warnings": warnings,
            "has_direct_evidence": has_direct_evidence,
        }

    # ------------------------------------------------------------
    # evidence check
    # ------------------------------------------------------------

    def _has_enough_direct_evidence(
        self,
        analysis: QueryAnalysis,
        has_direct_evidence: bool,
        sql_rows: list[dict[str, Any]],
        vector_docs: list[Any],
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
            return bool(sql_rows)

        if analysis.intent in {"admission_info", "event_info"}:
            return bool(sql_rows or vector_docs or has_direct_evidence)

        if analysis.intent == "comparison_info":
            if not vector_docs:
                return False

            target_depts = analysis.department_codes or []

            if not target_depts:
                return has_direct_evidence

            found_depts = {
                self._get_vector_metadata(doc).get("dept")
                for doc in vector_docs
            }

            return all(dept in found_depts for dept in target_depts)

        if analysis.intent == "recommendation_info":
            if not vector_docs:
                return False

            found_depts = {
                self._get_vector_metadata(doc).get("dept")
                for doc in vector_docs
                if self._get_vector_metadata(doc).get("dept")
            }

            return len(found_depts) >= 2

        if analysis.intent == "department_overview":
            if not vector_docs:
                return False

            if analysis.department_code:
                return any(
                    self._get_vector_metadata(doc).get("dept") == analysis.department_code
                    for doc in vector_docs
                )

            return has_direct_evidence

        return has_direct_evidence or bool(sql_rows or vector_docs)

    # ------------------------------------------------------------
    # extract helpers
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

    def _extract_vector_docs(self, vector_result: Any | None) -> list[Any]:
        if vector_result is None:
            return []

        results = getattr(vector_result, "results", None)

        if results is not None:
            return list(results)

        documents = getattr(vector_result, "documents", None)

        if documents is not None:
            return list(documents)

        if isinstance(vector_result, dict):
            return list(vector_result.get("results") or vector_result.get("documents") or [])

        return []

    def _get_vector_metadata(self, item: Any) -> dict[str, Any]:
        if hasattr(item, "document"):
            document = item.document
        else:
            document = item

        metadata = getattr(document, "metadata", None)

        if isinstance(metadata, dict):
            return metadata

        if isinstance(item, dict):
            metadata = item.get("metadata")

            if isinstance(metadata, dict):
                return metadata

        return {}

    def _extract_warnings(self, obj: Any | None) -> list[str]:
        if obj is None:
            return []

        if isinstance(obj, dict):
            warnings = obj.get("warnings") or []
            return [str(w) for w in warnings if w]

        warnings = getattr(obj, "warnings", [])

        return [str(w) for w in warnings if w]

    def _deduplicate_strings(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            value = str(value).strip()

            if not value:
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
    from src.rag.context_builder import ContextBuilder

    analyzer = QuestionAnalyzer()
    generator = AnswerGenerator()
    builder = ContextBuilder()

    question = "AI대학 학과별 홈페이지 URL을 정리해줘."
    analysis = analyzer.analyze(question)

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
            {
                "dept": "ax",
                "dept_name": "AX학과",
                "homepage_url": "https://ax.kaist.ac.kr/",
                "source": "manual_seed",
            },
            {
                "dept": "fx",
                "dept_name": "AI미래학과",
                "homepage_url": "https://fx.kaist.ac.kr/",
                "source": "manual_seed",
            },
        ],
        "warnings": [],
    }

    context = builder.build(
        question=question,
        analysis=analysis,
        sql_result=mock_sql_result,
        vector_result=None,
    )

    result = generator.generate(
        question=question,
        context=context,
        analysis=analysis,
        sql_result=mock_sql_result,
        vector_result=None,
    )

    print(result["answer"])
    print("\n[SOURCES]")
    for source in result["sources"]:
        print(source)