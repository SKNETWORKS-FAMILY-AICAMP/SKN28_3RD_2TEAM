from __future__ import annotations

import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT_FROM_FILE = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT_FROM_FILE) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FROM_FILE))

from src.rag.query_analyzer import QuestionAnalyzer, QueryAnalysis


if TYPE_CHECKING:
    from langchain_core.documents import Document


# ============================================================
# 1. 타입 정의
# ============================================================

VectorSearchStatus = Literal[
    "searched",
    "skipped_sql_route",
    "need_clarification",
    "no_result",
    "error",
]

SearchStage = Literal[
    "strict_filter",
    "department_only",
    "content_type_only",
    "multi_department_balanced",
    "recommendation_balanced",
    "no_filter",
]

FallbackTriggerMode = Literal[
    "only_when_empty",
    "below_min_results",
]


# ============================================================
# 2. 검색 scope 정책
# ============================================================

AI_COLLEGE_DEPT_CODES = {
    "aic",
    "ai_systems",
    "ax",
    "fx",
}

AI_COLLEGE_DEPT_ORDER = [
    "aic",
    "ai_systems",
    "ax",
    "fx",
]

AI_COLLEGE_DEPT_NAMES = {
    "AI컴퓨팅학과",
    "AI시스템학과",
    "AX학과",
    "AI미래학과",
}

AI_COLLEGE_SCOPE_KEYWORDS = [
    "AI대학",
    "AI 대학",
    "KAIST AI대학",
    "카이스트 AI대학",
    "AI College",
    "AI college",
    "AI 관련 학과",
    "전체 학과",
    "모든 학과",
    "각 학과",
    "학과별",
    "학과들",
    "학과들을",
]

KAIST_GLOBAL_SOURCE_TYPES = {
    "csv_kaist_profile",
    "csv_kaist_statistics",
    "csv_kaist_link",
}

KAIST_OFFICE_SOURCE_TYPES = {
    "csv_department_office",
}


# ============================================================
# 3. 설정 / 결과 dataclass
# ============================================================

@dataclass
class VectorRetrieverConfig:
    project_root: Path = PROJECT_ROOT_FROM_FILE
    chroma_relative_dir: Path = Path("data") / "vectorstore" / "chroma_db"
    collection_name: str = "kaist_graduate_info"
    embedding_model: str = "text-embedding-3-small"

    search_k: int = 5
    fetch_k: int = 25
    candidate_multiplier: int = 4
    min_results_before_fallback: int = 2

    use_rewritten_question: bool = True
    use_fallback: bool = True
    fallback_trigger_mode: FallbackTriggerMode = "below_min_results"
    use_lightweight_reranker: bool = True

    # 비교/추천 질문에서 학과별로 가져올 문서 수
    per_department_k: int = 3

    @property
    def chroma_dir(self) -> Path:
        return self.project_root / self.chroma_relative_dir


@dataclass
class RetrievedVectorDocument:
    document: Document
    score: float | None
    search_stage: SearchStage
    rerank_score: float = 0.0

    def to_debug_dict(self) -> dict[str, Any]:
        metadata = self.document.metadata

        return {
            "score": self.score,
            "rerank_score": self.rerank_score,
            "search_stage": self.search_stage,
            "metadata": {
                "source_type": metadata.get("source_type"),
                "dept": metadata.get("dept"),
                "dept_name": metadata.get("dept_name"),
                "content_type": metadata.get("content_type"),
                "title": metadata.get("title"),
                "source": metadata.get("source") or metadata.get("source_url"),
            },
            "preview": self.document.page_content[:500],
        }


@dataclass
class SearchAttempt:
    search_stage: SearchStage
    metadata_filter: dict[str, Any] | None
    result_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VectorRetrievalResult:
    status: VectorSearchStatus
    message: str
    analysis: QueryAnalysis

    results: list[RetrievedVectorDocument] = field(default_factory=list)
    used_query: str | None = None
    used_filter: dict[str, Any] | None = None
    used_fallback: bool = False
    search_attempts: list[SearchAttempt] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def documents(self) -> list[Document]:
        return [item.document for item in self.results]

    @property
    def scores(self) -> list[float | None]:
        return [item.score for item in self.results]

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "used_query": self.used_query,
            "used_filter": self.used_filter,
            "used_fallback": self.used_fallback,
            "warnings": self.warnings,
            "search_attempts": [attempt.to_dict() for attempt in self.search_attempts],
            "analysis": self.analysis.to_dict(),
            "results": [item.to_debug_dict() for item in self.results],
        }


# ============================================================
# 4. Lightweight reranker
# ============================================================

class LightweightReranker:
    STOPWORDS = {
        "알려줘",
        "보여줘",
        "정리해줘",
        "설명해줘",
        "정보",
        "관련",
        "대한",
        "어떤",
        "무엇",
        "뭐야",
        "목록",
        "전체",
        "각",
        "및",
        "그리고",
        "또",
        "도",
        "있는",
        "없는",
        "합니다",
        "해주세요",
        "문서",
        "나와",
        "있어",
    }

    def rerank(
        self,
        question: str,
        analysis: QueryAnalysis,
        items: list[RetrievedVectorDocument],
    ) -> list[RetrievedVectorDocument]:
        question_keywords = self._extract_keywords(question)

        for item in items:
            item.rerank_score = self._calculate_score(
                question_keywords=question_keywords,
                analysis=analysis,
                item=item,
            )

        return sorted(items, key=lambda item: item.rerank_score, reverse=True)

    def _calculate_score(
        self,
        question_keywords: set[str],
        analysis: QueryAnalysis,
        item: RetrievedVectorDocument,
    ) -> float:
        document = item.document
        metadata = document.metadata

        document_text = self._build_document_text(document)
        document_keywords = self._extract_keywords(document_text)

        keyword_score = self._keyword_overlap_score(
            question_keywords,
            document_keywords,
        )
        metadata_score = self._metadata_match_score(analysis, metadata)
        vector_score = self._normalized_vector_score(item.score)
        stage_score = self._stage_score(item.search_stage)

        final_score = (
            keyword_score * 0.35
            + metadata_score * 0.30
            + vector_score * 0.20
            + stage_score * 0.15
        )

        return round(final_score, 6)

    def _build_document_text(self, document: Document) -> str:
        metadata = document.metadata

        keys = [
            "dept_name",
            "department",
            "content_type",
            "doc_type",
            "source_type",
            "title",
            "section",
            "admission_type",
            "course_code",
            "course_type",
            "tracks",
            "name",
            "role",
            "email",
            "phone",
            "homepage",
            "event_date",
            "file_name",
        ]

        metadata_text = " ".join(
            str(metadata[key])
            for key in keys
            if metadata.get(key)
        )

        return f"{metadata_text}\n{document.page_content}"

    def _extract_keywords(self, text: str) -> set[str]:
        tokens = re.findall(r"[가-힣a-zA-Z0-9_]+", str(text).lower())

        return {
            token
            for token in tokens
            if len(token) >= 2 and token not in self.STOPWORDS
        }

    def _keyword_overlap_score(
        self,
        question_keywords: set[str],
        document_keywords: set[str],
    ) -> float:
        if not question_keywords:
            return 0.0

        overlap = question_keywords.intersection(document_keywords)

        return len(overlap) / len(question_keywords)

    def _metadata_match_score(
        self,
        analysis: QueryAnalysis,
        metadata: dict[str, Any],
    ) -> float:
        score = 0.0
        max_score = 0.0

        # 단일 학과 질문
        if analysis.department_code:
            max_score += 1.0
            if metadata.get("dept") == analysis.department_code:
                score += 1.0

        # 다중 학과 질문
        if analysis.department_codes:
            max_score += 1.0
            if metadata.get("dept") in analysis.department_codes:
                score += 1.0

        # content_type이 강한 질문
        if analysis.content_type:
            max_score += 1.0
            if metadata.get("content_type") == analysis.content_type:
                score += 1.0

        if max_score == 0:
            return 0.0

        return score / max_score

    def _normalized_vector_score(self, vector_score: float | None) -> float:
        if vector_score is None:
            return 0.0

        vector_score = max(vector_score, 0.0)

        # Chroma distance는 작을수록 유사함
        return 1 / (1 + vector_score)

    def _stage_score(self, search_stage: SearchStage) -> float:
        scores = {
            "strict_filter": 1.0,
            "multi_department_balanced": 0.95,
            "recommendation_balanced": 0.90,
            "department_only": 0.65,
            "content_type_only": 0.50,
            "no_filter": 0.25,
        }

        return scores.get(search_stage, 0.0)


# ============================================================
# 5. VectorRetriever
# ============================================================

class VectorRetriever:
    def __init__(
        self,
        config: VectorRetrieverConfig | None = None,
        question_analyzer: QuestionAnalyzer | None = None,
        reranker: LightweightReranker | None = None,
    ) -> None:
        load_dotenv()

        self.config = config or VectorRetrieverConfig()
        self.question_analyzer = question_analyzer or QuestionAnalyzer()
        self.reranker = reranker or LightweightReranker()

        self._validate_settings()

        from langchain_chroma import Chroma
        from langchain_openai import OpenAIEmbeddings

        self.embedding_model = OpenAIEmbeddings(
            model=self.config.embedding_model,
            request_timeout=30,
            max_retries=2,
        )

        self.vectorstore = Chroma(
            collection_name=self.config.collection_name,
            embedding_function=self.embedding_model,
            persist_directory=str(self.config.chroma_dir),
        )

    # ------------------------------------------------------------
    # public API
    # ------------------------------------------------------------

    def retrieve(
        self,
        question: str,
        previous_department_code: str | None = None,
        force_vector_search: bool = False,
        analysis: QueryAnalysis | None = None,
    ) -> VectorRetrievalResult:
        """
        Vector 검색 실행.

        중요:
        - analysis가 들어오면 재분석하지 않고 그대로 사용한다.
        - analysis가 없으면 하위 호환을 위해 내부에서 analyze한다.
        """
        try:
            if analysis is None:
                analysis = self.question_analyzer.analyze(
                    question=question,
                    previous_department_code=previous_department_code,
                )

            if analysis.route == "clarify":
                return VectorRetrievalResult(
                    status="need_clarification",
                    message="질문에 필요한 정보가 부족해서 추가 질문이 필요합니다.",
                    analysis=analysis,
                    used_filter=analysis.metadata_filter,
                )

            if analysis.route == "sql" and not force_vector_search:
                return VectorRetrievalResult(
                    status="skipped_sql_route",
                    message="SQL 조회가 더 적합한 질문이므로 vector 검색을 생략했습니다.",
                    analysis=analysis,
                    used_filter=analysis.metadata_filter,
                )

            search_query = self._select_search_query(analysis)

            if analysis.intent == "comparison_info":
                return self._retrieve_for_comparison(
                    analysis=analysis,
                    search_query=search_query,
                )

            if analysis.intent == "recommendation_info":
                return self._retrieve_for_recommendation(
                    analysis=analysis,
                    search_query=search_query,
                )

            search_plan = self._build_search_plan(analysis)

            items, attempts, used_fallback, warnings = self._search_with_fallback(
                search_query=search_query,
                search_plan=search_plan,
                analysis=analysis,
            )

            if not items:
                return VectorRetrievalResult(
                    status="no_result",
                    message="Vectorstore에서 관련 문서를 찾지 못했습니다.",
                    analysis=analysis,
                    used_query=search_query,
                    used_filter=analysis.metadata_filter,
                    used_fallback=used_fallback,
                    search_attempts=attempts,
                    warnings=warnings,
                )

            reranked_items = self._rerank_results(
                question=analysis.normalized_question,
                analysis=analysis,
                items=items,
            )

            final_items = self._select_final_results(
                analysis=analysis,
                items=reranked_items,
            )

            return VectorRetrievalResult(
                status="searched",
                message="Vector 검색이 완료되었습니다.",
                analysis=analysis,
                results=final_items,
                used_query=search_query,
                used_filter=analysis.metadata_filter,
                used_fallback=used_fallback,
                search_attempts=attempts,
                warnings=warnings,
            )

        except Exception as error:
            fallback_analysis = analysis or self.question_analyzer.analyze(question)

            return VectorRetrievalResult(
                status="error",
                message="Vector 검색 중 오류가 발생했습니다.",
                analysis=fallback_analysis,
                warnings=[f"{type(error).__name__}: {error}"],
            )

    def search(
        self,
        question: str,
        previous_department_code: str | None = None,
        force_vector_search: bool = False,
        analysis: QueryAnalysis | None = None,
    ) -> VectorRetrievalResult:
        return self.retrieve(
            question=question,
            previous_department_code=previous_department_code,
            force_vector_search=force_vector_search,
            analysis=analysis,
        )

    def __call__(
        self,
        question: str,
        previous_department_code: str | None = None,
        force_vector_search: bool = False,
        analysis: QueryAnalysis | None = None,
    ) -> VectorRetrievalResult:
        return self.retrieve(
            question=question,
            previous_department_code=previous_department_code,
            force_vector_search=force_vector_search,
            analysis=analysis,
        )

    # ------------------------------------------------------------
    # specialized retrieval
    # ------------------------------------------------------------

    def _retrieve_for_comparison(
        self,
        analysis: QueryAnalysis,
        search_query: str,
    ) -> VectorRetrievalResult:
        """
        학과 비교 질문은 학과별로 균등 검색한다.

        예:
            AI컴퓨팅학과와 AX학과를 비교해줘
        → aic k개 + ax k개를 따로 검색
        """
        dept_codes = analysis.department_codes or AI_COLLEGE_DEPT_ORDER

        items: list[RetrievedVectorDocument] = []
        attempts: list[SearchAttempt] = []
        warnings: list[str] = []

        for dept_code in dept_codes:
            metadata_filter = {"dept": dept_code}

            dept_items = self._similarity_search(
                query=search_query,
                metadata_filter=metadata_filter,
                k=self.config.per_department_k,
                search_stage="multi_department_balanced",
            )

            attempts.append(
                SearchAttempt(
                    search_stage="multi_department_balanced",
                    metadata_filter=metadata_filter,
                    result_count=len(dept_items),
                )
            )

            items.extend(dept_items)

        if not items and self.config.use_fallback:
            fallback_items = self._similarity_search(
                query=search_query,
                metadata_filter=None,
                k=self.config.fetch_k,
                search_stage="no_filter",
            )
            attempts.append(
                SearchAttempt(
                    search_stage="no_filter",
                    metadata_filter=None,
                    result_count=len(fallback_items),
                )
            )
            items.extend(fallback_items)
            warnings.append("비교 대상 학과별 검색 결과가 부족하여 no_filter fallback을 사용했습니다.")

        if not items:
            return VectorRetrievalResult(
                status="no_result",
                message="비교 질문에 사용할 vector 문서를 찾지 못했습니다.",
                analysis=analysis,
                used_query=search_query,
                used_filter=None,
                used_fallback=True,
                search_attempts=attempts,
                warnings=warnings,
            )

        items = self._deduplicate_items(items)
        items = self._filter_scope_items(analysis, items)

        reranked_items = self._rerank_results(
            question=analysis.normalized_question,
            analysis=analysis,
            items=items,
        )

        final_items = self._select_balanced_by_department(
            items=reranked_items,
            dept_codes=dept_codes,
            per_department_k=self.config.per_department_k,
        )

        return VectorRetrievalResult(
            status="searched",
            message="비교 질문용 학과별 균등 vector 검색이 완료되었습니다.",
            analysis=analysis,
            results=final_items,
            used_query=search_query,
            used_filter={"dept_codes": dept_codes},
            used_fallback=False,
            search_attempts=attempts,
            warnings=warnings,
        )

    def _retrieve_for_recommendation(
        self,
        analysis: QueryAnalysis,
        search_query: str,
    ) -> VectorRetrievalResult:
        """
        추천 질문은 특정 학과가 없더라도 전체 4개 학과에서 균등하게 근거를 가져온다.
        """
        dept_codes = AI_COLLEGE_DEPT_ORDER

        items: list[RetrievedVectorDocument] = []
        attempts: list[SearchAttempt] = []
        warnings: list[str] = []

        for dept_code in dept_codes:
            metadata_filter = {"dept": dept_code}

            dept_items = self._similarity_search(
                query=search_query,
                metadata_filter=metadata_filter,
                k=self.config.per_department_k,
                search_stage="recommendation_balanced",
            )

            attempts.append(
                SearchAttempt(
                    search_stage="recommendation_balanced",
                    metadata_filter=metadata_filter,
                    result_count=len(dept_items),
                )
            )

            items.extend(dept_items)

        if not items and self.config.use_fallback:
            fallback_items = self._similarity_search(
                query=search_query,
                metadata_filter=None,
                k=self.config.fetch_k,
                search_stage="no_filter",
            )
            attempts.append(
                SearchAttempt(
                    search_stage="no_filter",
                    metadata_filter=None,
                    result_count=len(fallback_items),
                )
            )
            items.extend(fallback_items)
            warnings.append("추천 질문에서 학과별 검색 결과가 부족하여 no_filter fallback을 사용했습니다.")

        if not items:
            return VectorRetrievalResult(
                status="no_result",
                message="추천 질문에 사용할 vector 문서를 찾지 못했습니다.",
                analysis=analysis,
                used_query=search_query,
                used_filter={"dept_codes": dept_codes},
                used_fallback=True,
                search_attempts=attempts,
                warnings=warnings,
            )

        items = self._deduplicate_items(items)
        items = self._filter_scope_items(analysis, items)

        reranked_items = self._rerank_results(
            question=analysis.normalized_question,
            analysis=analysis,
            items=items,
        )

        final_items = self._select_balanced_by_department(
            items=reranked_items,
            dept_codes=dept_codes,
            per_department_k=2,
        )

        return VectorRetrievalResult(
            status="searched",
            message="추천 질문용 학과별 균등 vector 검색이 완료되었습니다.",
            analysis=analysis,
            results=final_items,
            used_query=search_query,
            used_filter={"dept_codes": dept_codes},
            used_fallback=False,
            search_attempts=attempts,
            warnings=warnings,
        )

    # ------------------------------------------------------------
    # search internals
    # ------------------------------------------------------------

    def _select_search_query(self, analysis: QueryAnalysis) -> str:
        if self.config.use_rewritten_question and analysis.rewritten_question:
            return analysis.rewritten_question

        return analysis.normalized_question

    def _build_search_plan(
        self,
        analysis: QueryAnalysis,
    ) -> list[tuple[SearchStage, dict[str, Any] | None]]:
        """
        일반 질문의 fallback 검색 계획.

        strict_filter:
            dept + content_type
        department_only:
            dept
        content_type_only:
            content_type
        no_filter:
            filter 없음
        """
        strict_filter = analysis.metadata_filter or None

        department_only = None
        if analysis.department_code:
            department_only = {"dept": analysis.department_code}

        content_type_only = None
        if analysis.content_type:
            content_type_only = {"content_type": analysis.content_type}

        plan: list[tuple[SearchStage, dict[str, Any] | None]] = []

        if strict_filter:
            plan.append(("strict_filter", strict_filter))

        if department_only and department_only != strict_filter:
            plan.append(("department_only", department_only))

        if content_type_only and content_type_only != strict_filter:
            plan.append(("content_type_only", content_type_only))

        plan.append(("no_filter", None))

        return plan

    def _search_with_fallback(
        self,
        search_query: str,
        search_plan: list[tuple[SearchStage, dict[str, Any] | None]],
        analysis: QueryAnalysis,
    ) -> tuple[
        list[RetrievedVectorDocument],
        list[SearchAttempt],
        bool,
        list[str],
    ]:
        attempts: list[SearchAttempt] = []
        warnings: list[str] = []
        used_fallback = False

        all_items: list[RetrievedVectorDocument] = []

        for index, (stage, metadata_filter) in enumerate(search_plan):
            k = self._candidate_k()

            items = self._similarity_search(
                query=search_query,
                metadata_filter=metadata_filter,
                k=k,
                search_stage=stage,
            )

            attempts.append(
                SearchAttempt(
                    search_stage=stage,
                    metadata_filter=metadata_filter,
                    result_count=len(items),
                )
            )

            if items:
                all_items.extend(items)

            enough_results = self._has_enough_results(all_items)

            if enough_results:
                break

            if not self.config.use_fallback:
                break

            if index < len(search_plan) - 1:
                used_fallback = True

        all_items = self._deduplicate_items(all_items)
        all_items = self._filter_scope_items(analysis, all_items)

        if used_fallback:
            warnings.append(
                "초기 metadata filter 검색 결과가 부족하여 fallback 검색을 함께 사용했습니다. "
                "fallback 결과는 질문의 직접 근거인지 확인이 필요합니다."
            )

        return all_items, attempts, used_fallback, warnings

    def _similarity_search(
        self,
        query: str,
        metadata_filter: dict[str, Any] | None,
        k: int,
        search_stage: SearchStage,
    ) -> list[RetrievedVectorDocument]:
        """
        Chroma similarity_search_with_score 래퍼.
        """
        if metadata_filter:
            raw_results = self.vectorstore.similarity_search_with_score(
                query,
                k=k,
                filter=metadata_filter,
            )
        else:
            raw_results = self.vectorstore.similarity_search_with_score(
                query,
                k=k,
            )

        return [
            RetrievedVectorDocument(
                document=doc,
                score=score,
                search_stage=search_stage,
            )
            for doc, score in raw_results
        ]

    def _candidate_k(self) -> int:
        return max(
            self.config.fetch_k,
            self.config.search_k * self.config.candidate_multiplier,
        )

    def _has_enough_results(self, items: list[RetrievedVectorDocument]) -> bool:
        if self.config.fallback_trigger_mode == "only_when_empty":
            return len(items) > 0

        return len(items) >= self.config.min_results_before_fallback

    # ------------------------------------------------------------
    # rerank / select
    # ------------------------------------------------------------

    def _rerank_results(
        self,
        question: str,
        analysis: QueryAnalysis,
        items: list[RetrievedVectorDocument],
    ) -> list[RetrievedVectorDocument]:
        if not self.config.use_lightweight_reranker:
            return items

        return self.reranker.rerank(
            question=question,
            analysis=analysis,
            items=items,
        )

    def _select_final_results(
        self,
        analysis: QueryAnalysis,
        items: list[RetrievedVectorDocument],
    ) -> list[RetrievedVectorDocument]:
        if not items:
            return []

        if analysis.intent in {"comparison_info", "recommendation_info"}:
            dept_codes = analysis.department_codes or AI_COLLEGE_DEPT_ORDER

            return self._select_balanced_by_department(
                items=items,
                dept_codes=dept_codes,
                per_department_k=self.config.per_department_k,
            )

        return items[: self.config.search_k]

    def _select_balanced_by_department(
        self,
        items: list[RetrievedVectorDocument],
        dept_codes: list[str],
        per_department_k: int,
    ) -> list[RetrievedVectorDocument]:
        selected: list[RetrievedVectorDocument] = []
        used_hashes: set[str] = set()

        for dept_code in dept_codes:
            dept_items = [
                item
                for item in items
                if item.document.metadata.get("dept") == dept_code
            ]

            for item in dept_items[:per_department_k]:
                item_hash = self._item_hash(item)

                if item_hash in used_hashes:
                    continue

                selected.append(item)
                used_hashes.add(item_hash)

        # 학과별 선택 후에도 부족하면 전체 상위 결과로 보충
        if len(selected) < self.config.search_k:
            for item in items:
                item_hash = self._item_hash(item)

                if item_hash in used_hashes:
                    continue

                selected.append(item)
                used_hashes.add(item_hash)

                if len(selected) >= self.config.search_k:
                    break

        return selected[: max(self.config.search_k, len(dept_codes) * per_department_k)]

    # ------------------------------------------------------------
    # filters / dedupe
    # ------------------------------------------------------------

    def _deduplicate_items(
        self,
        items: list[RetrievedVectorDocument],
    ) -> list[RetrievedVectorDocument]:
        deduped: list[RetrievedVectorDocument] = []
        seen_hashes: set[str] = set()

        for item in items:
            item_hash = self._item_hash(item)

            if item_hash in seen_hashes:
                continue

            seen_hashes.add(item_hash)
            deduped.append(item)

        return deduped

    def _item_hash(self, item: RetrievedVectorDocument) -> str:
        metadata = item.document.metadata
        content_hash = metadata.get("content_hash")

        if content_hash:
            return str(content_hash)

        return f"{metadata.get('source_type')}|{metadata.get('dept')}|{metadata.get('title')}|{item.document.page_content[:300]}"

    def _filter_scope_items(
        self,
        analysis: QueryAnalysis,
        items: list[RetrievedVectorDocument],
    ) -> list[RetrievedVectorDocument]:
        """
        KAIST AI College 범위 밖 문서를 줄인다.

        단, KAIST 전체 정보와 학과사무실 정보는 dept가 없을 수 있으므로 허용한다.
        """
        if not items:
            return []

        filtered: list[RetrievedVectorDocument] = []

        for item in items:
            metadata = item.document.metadata
            dept = metadata.get("dept")
            dept_name = metadata.get("dept_name")
            source_type = metadata.get("source_type")

            if dept in AI_COLLEGE_DEPT_CODES:
                filtered.append(item)
                continue

            if dept_name in AI_COLLEGE_DEPT_NAMES:
                filtered.append(item)
                continue

            if source_type in KAIST_GLOBAL_SOURCE_TYPES:
                filtered.append(item)
                continue

            if source_type in KAIST_OFFICE_SOURCE_TYPES:
                filtered.append(item)
                continue

            # 질문이 KAIST 전체 정보면 global 문서 허용
            if analysis.intent in {
                "kaist_profile_info",
                "kaist_statistics_info",
                "kaist_link_info",
            }:
                filtered.append(item)
                continue

        return filtered or items

    # ------------------------------------------------------------
    # validation / utility
    # ------------------------------------------------------------

    def _validate_settings(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요."
            )

        if not self.config.chroma_dir.exists():
            print(
                "[경고] Chroma DB 폴더가 아직 없습니다. "
                f"먼저 data/build_vectorstore.py를 실행하세요: {self.config.chroma_dir}"
            )


# ============================================================
# 6. 수동 테스트
# ============================================================

if __name__ == "__main__":
    retriever = VectorRetriever()

    questions = [
        "AI미래학과는 어떤 인재를 양성하려고 해?",
        "AI컴퓨팅학과와 AX학과를 비교해줘.",
        "나는 AI 서비스 적용에 관심이 있는데 어떤 학과가 맞아?",
        "AI시스템학과의 교육과정을 알려줘.",
    ]

    for question in questions:
        print("=" * 100)
        print("Q:", question)

        result = retriever.retrieve(question)

        print("status:", result.status)
        print("message:", result.message)
        print("intent:", result.analysis.intent)
        print("dept:", result.analysis.department_code)
        print("dept_codes:", result.analysis.department_codes)
        print("used_query:", result.used_query)
        print("used_filter:", result.used_filter)
        print("used_fallback:", result.used_fallback)
        print("attempts:", [attempt.to_dict() for attempt in result.search_attempts])
        print("warnings:", result.warnings)

        for idx, item in enumerate(result.results, start=1):
            print("-" * 100)
            print(f"[{idx}] score={item.score}, rerank={item.rerank_score}, stage={item.search_stage}")
            print(item.to_debug_dict()["metadata"])
            print(item.document.page_content[:500])