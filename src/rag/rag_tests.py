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

from src.rag.query_analyzer import QuestionAnalyzer
from src.rag.vector_retriever import VectorRetriever
from src.rag.context_builder import ContextBuilder, ContextBuilderConfig
from src.rag.answer_generator import AnswerGenerator


RUN_LLM_ANSWER = False
SAVE_REPORT = True

REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "reports" / "rag_test_results.json"


@dataclass
class TestQuestion:
    question: str
    expected_route: str | None = None
    memo: str = ""


@dataclass
class TestResult:
    question: str
    expected_route: str | None
    actual_route: str
    route_ok: bool | None
    retrieval_status: str | None
    used_fallback: bool
    warnings: list[str]
    top_sources: list[dict[str, Any]]
    answer_preview: str = ""


TEST_QUESTIONS = [
    TestQuestion(
        question="AI컴퓨팅학과 석사 지원 자격은?",
        expected_route="vector",
        memo="입학 지원 자격 문서 검색",
    ),
    TestQuestion(
        question="AI컴퓨팅학과 박사 지원 자격은?",
        expected_route="vector",
        memo="박사과정 입학 조건",
    ),
    TestQuestion(
        question="AI컴퓨팅학과 학과설명회 정보 알려줘",
        expected_route="vector",
        memo="event 문서 검색",
    ),
    TestQuestion(
        question="AI컴퓨팅학과는 어떤 학과야?",
        expected_route="vector",
        memo="학과 소개/개요",
    ),
    TestQuestion(
        question="AI시스템학과 교과목 알려줘",
        expected_route="sql",
        memo="교과목 목록은 SQL",
    ),
    TestQuestion(
        question="AI시스템학과 교과목 목록과 각 과목 설명도 알려줘",
        expected_route="hybrid",
        memo="SQL + Vector",
    ),
    TestQuestion(
        question="AX학과 교수진 이메일 목록 보여줘",
        expected_route="sql",
        memo="교수진 이메일 목록은 SQL",
    ),
    TestQuestion(
        question="AX학과 교수 연구분야도 설명해줘",
        expected_route="hybrid",
        memo="교수 목록 + 설명",
    ),
    TestQuestion(
        question="KAIST 학과 사무실 전화번호 알려줘",
        expected_route="sql",
        memo="전체 사무실 전화번호",
    ),
    TestQuestion(
        question="자료 다운로드 링크 알려줘",
        expected_route="sql",
        memo="전체 자료/링크 조회",
    ),
    TestQuestion(
        question="교수진도 알려줘",
        expected_route="clarify",
        memo="학과 누락",
    ),
    TestQuestion(
        question="입학 조건은?",
        expected_route="clarify",
        memo="학과 누락",
    ),
    TestQuestion(
        question="AI미래학과 입학 일정 알려줘",
        expected_route="vector",
        memo="학과 + 입학 일정",
    ),
    TestQuestion(
        question="AX학과 설명회 일정 표로 정리하고 근거도 알려줘",
        expected_route="hybrid",
        memo="표 + 근거",
    ),
]


def build_top_sources(vector_result) -> list[dict[str, Any]]:
    if vector_result is None:
        return []

    sources = []

    for item in vector_result.results[:3]:
        metadata = item.document.metadata

        sources.append(
            {
                "title": metadata.get("title"),
                "dept": metadata.get("dept"),
                "dept_name": metadata.get("dept_name"),
                "content_type": metadata.get("content_type"),
                "source": metadata.get("source") or metadata.get("source_url"),
                "search_stage": item.search_stage,
                "score": item.score,
                "rerank_score": item.rerank_score,
            }
        )

    return sources


def run_single_test(
    test_case: TestQuestion,
    analyzer: QuestionAnalyzer,
    retriever: VectorRetriever,
    context_builder: ContextBuilder,
    answer_generator: AnswerGenerator | None = None,
) -> TestResult:
    analysis = analyzer.analyze(test_case.question)

    route_ok = None
    if test_case.expected_route:
        route_ok = analysis.route == test_case.expected_route

    vector_result = retriever.retrieve(test_case.question)

    built_context = context_builder.build(
        analysis=vector_result.analysis,
        vector_result=vector_result,
    )

    answer_preview = ""

    if RUN_LLM_ANSWER and answer_generator:
        if analysis.route in {"vector", "hybrid", "clarify"}:
            generated = answer_generator.generate(
                question=test_case.question,
                built_context=built_context,
                analysis=vector_result.analysis,
            )
            answer_preview = generated.answer[:500]

    return TestResult(
        question=test_case.question,
        expected_route=test_case.expected_route,
        actual_route=analysis.route,
        route_ok=route_ok,
        retrieval_status=vector_result.status,
        used_fallback=vector_result.used_fallback,
        warnings=vector_result.warnings,
        top_sources=build_top_sources(vector_result),
        answer_preview=answer_preview,
    )


def print_result(result: TestResult) -> None:
    print("=" * 100)
    print("질문:", result.question)
    print("expected_route:", result.expected_route)
    print("actual_route:", result.actual_route)
    print("route_ok:", result.route_ok)
    print("retrieval_status:", result.retrieval_status)
    print("used_fallback:", result.used_fallback)

    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print("-", warning)

    print("top_sources:")
    for source in result.top_sources:
        print(
            "-",
            source.get("dept_name"),
            source.get("content_type"),
            source.get("title"),
            "| stage:",
            source.get("search_stage"),
            "| rerank:",
            source.get("rerank_score"),
        )

    if result.answer_preview:
        print("answer_preview:")
        print(result.answer_preview)


def save_report(results: list[TestResult]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    data = [asdict(result) for result in results]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n저장 완료:", REPORT_PATH)


def print_summary(results: list[TestResult]) -> None:
    total_count = len(results)
    route_checked = [result for result in results if result.route_ok is not None]
    route_passed = [result for result in route_checked if result.route_ok]

    fallback_count = sum(result.used_fallback for result in results)
    warning_count = sum(1 for result in results if result.warnings)

    print("\n" + "=" * 100)
    print("[SUMMARY]")
    print("total:", total_count)
    print("route checked:", len(route_checked))
    print("route passed:", len(route_passed))
    print("fallback used:", fallback_count)
    print("warnings:", warning_count)

    failed_routes = [
        result
        for result in results
        if result.route_ok is False
    ]

    if failed_routes:
        print("\n[ROUTE FAILED]")
        for result in failed_routes:
            print(
                "-",
                result.question,
                "| expected:",
                result.expected_route,
                "| actual:",
                result.actual_route,
            )


def main() -> None:
    analyzer = QuestionAnalyzer()
    retriever = VectorRetriever()
    context_builder = ContextBuilder(
        ContextBuilderConfig(
            include_debug_info=False,
        )
    )

    answer_generator = AnswerGenerator() if RUN_LLM_ANSWER else None

    results = []

    for test_case in TEST_QUESTIONS:
        result = run_single_test(
            test_case=test_case,
            analyzer=analyzer,
            retriever=retriever,
            context_builder=context_builder,
            answer_generator=answer_generator,
        )

        results.append(result)
        print_result(result)

    print_summary(results)

    if SAVE_REPORT:
        save_report(results)


if __name__ == "__main__":
    main()