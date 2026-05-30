from __future__ import annotations

import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT_FROM_FILE = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT_FROM_FILE) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FROM_FILE))

from src.rag.query_analyzer import QuestionAnalyzer, QueryAnalysis


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
    "no_filter",
]

FallbackTriggerMode = Literal[
    "only_when_empty",
    "below_min_results",
]


@dataclass
class VectorRetrieverConfig:
    project_root: Path = Path(r"C:\Users\Playdata\workspace\SKN28-third-2TEAM")
    chroma_relative_dir: Path = Path("data") / "vectorstore" / "chroma_db"
    collection_name: str = "kaist_graduate_info"
    embedding_model: str = "text-embedding-3-small"

    search_k: int = 5
    fetch_k: int = 10
    min_results_before_fallback: int = 2

    use_rewritten_question: bool = True
    use_fallback: bool = True
    fallback_trigger_mode: FallbackTriggerMode = "only_when_empty"
    use_lightweight_reranker: bool = True

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
                "dept": metadata.get("dept"),
                "dept_name": metadata.get("dept_name"),
                "content_type": metadata.get("content_type"),
                "title": metadata.get("title"),
                "section": metadata.get("section"),
                "admission_type": metadata.get("admission_type"),
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


class LightweightReranker:
    STOPWORDS = {
        "알려줘", "보여줘", "정리해줘", "설명해줘",
        "정보", "관련", "대한", "어떤", "무엇", "뭐야",
        "목록", "전체", "각", "및", "그리고", "또", "도",
        "있는", "없는", "합니다", "해주세요",
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
        program_score = self._program_type_score(analysis, item)
        vector_score = self._normalized_vector_score(item.score)
        stage_score = self._stage_score(item.search_stage)

        final_score = (
            keyword_score * 0.25
            + metadata_score * 0.25
            + program_score * 0.25
            + vector_score * 0.15
            + stage_score * 0.10
        )

        return round(final_score, 6)

    def _build_document_text(self, document: Document) -> str:
        metadata = document.metadata

        keys = [
            "dept_name", "department", "content_type", "doc_type",
            "title", "section", "admission_type",
            "course_code", "course_type", "tracks",
            "name", "role", "email", "event_date",
        ]

        metadata_text = " ".join(
            str(metadata[key])
            for key in keys
            if metadata.get(key)
        )

        return f"{metadata_text}\n{document.page_content}"

    def _extract_keywords(self, text: str) -> set[str]:
        tokens = re.findall(r"[가-힣a-zA-Z0-9_]+", text.lower())

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

        if analysis.department_code:
            max_score += 1.0
            if metadata.get("dept") == analysis.department_code:
                score += 1.0

        if analysis.content_type:
            max_score += 1.0
            if metadata.get("content_type") == analysis.content_type:
                score += 1.0

        if max_score == 0:
            return 0.0

        return score / max_score

    def _program_type_score(
        self,
        analysis: QueryAnalysis,
        item: RetrievedVectorDocument,
    ) -> float:
        program_type = getattr(analysis, "program_type", None)

        if not program_type:
            return 0.5

        metadata = item.document.metadata

        if metadata.get("content_type") != "admission":
            return 0.3

        title = str(metadata.get("title") or "")
        section = str(metadata.get("section") or "")
        admission_type = str(metadata.get("admission_type") or "")
        content = item.document.page_content[:1000]

        text = f"{title} {section} {admission_type} {content}".lower()
        compact_text = text.replace(" ", "")

        if program_type == "master":
            if "석사과정" in compact_text and "석박사" not in compact_text:
                return 1.0
            if "석사" in compact_text and "석박사" not in compact_text:
                return 0.85
            if "석박사" in compact_text or "통합과정" in compact_text:
                return 0.1
            return 0.4

        if program_type == "doctor":
            if "박사과정" in compact_text and "석박사" not in compact_text:
                return 1.0
            if "박사" in compact_text and "석박사" not in compact_text:
                return 0.85
            if "석박사" in compact_text or "통합과정" in compact_text:
                return 0.15
            return 0.4

        if program_type == "integrated":
            if "석박사" in compact_text or "통합과정" in compact_text:
                return 1.0
            if "석사" in compact_text and "박사" in compact_text:
                return 0.75
            return 0.25

        return 0.5

    def _normalized_vector_score(self, vector_score: float | None) -> float:
        if vector_score is None:
            return 0.0

        vector_score = max(vector_score, 0.0)

        return 1 / (1 + vector_score)

    def _stage_score(self, search_stage: SearchStage) -> float:
        scores = {
            "strict_filter": 1.0,
            "department_only": 0.65,
            "content_type_only": 0.50,
            "no_filter": 0.25,
        }

        return scores.get(search_stage, 0.0)


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

        self.embedding_model = OpenAIEmbeddings(
            model=self.config.embedding_model,
        )

        self.vectorstore = Chroma(
            collection_name=self.config.collection_name,
            embedding_function=self.embedding_model,
            persist_directory=str(self.config.chroma_dir),
        )

    def retrieve(
        self,
        question: str,
        previous_department_code: str | None = None,
        force_vector_search: bool = False,
    ) -> VectorRetrievalResult:
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
        search_plan = self._build_search_plan(analysis)

        items, attempts, used_fallback, warnings = self._search_with_fallback(
            search_query=search_query,
            search_plan=search_plan,
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

        return VectorRetrievalResult(
            status="searched",
            message="Vectorstore 검색이 완료되었습니다.",
            analysis=analysis,
            results=reranked_items[: self.config.search_k],
            used_query=search_query,
            used_filter=analysis.metadata_filter,
            used_fallback=used_fallback,
            search_attempts=attempts,
            warnings=warnings,
        )

    def retrieve_documents(
        self,
        question: str,
        previous_department_code: str | None = None,
        force_vector_search: bool = False,
    ) -> list[Document]:
        result = self.retrieve(
            question=question,
            previous_department_code=previous_department_code,
            force_vector_search=force_vector_search,
        )

        return result.documents

    def format_documents_for_context(
        self,
        documents: list[Document],
        max_chars_per_doc: int = 1500,
    ) -> str:
        blocks = []

        for index, document in enumerate(documents, start=1):
            metadata = document.metadata

            department = metadata.get("dept_name") or metadata.get("department") or ""
            content_type = metadata.get("content_type") or metadata.get("doc_type") or ""
            title = metadata.get("title") or ""
            source = metadata.get("source") or metadata.get("source_url") or ""

            content = document.page_content

            if len(content) > max_chars_per_doc:
                content = content[:max_chars_per_doc].rstrip() + "\n...[중략]"

            blocks.append(
                f"[문서 {index}]\n"
                f"학과: {department}\n"
                f"문서유형: {content_type}\n"
                f"제목: {title}\n"
                f"출처: {source}\n"
                f"내용:\n{content}"
            )

        return "\n\n".join(blocks)

    def _validate_settings(self) -> None:
        if not self.config.chroma_dir.exists():
            raise FileNotFoundError(
                f"Chroma DB 폴더를 찾을 수 없습니다: {self.config.chroma_dir}"
            )

        if not os.getenv("OPENAI_API_KEY"):
            raise EnvironmentError(
                "OPENAI_API_KEY가 설정되어 있지 않습니다."
            )

    def _select_search_query(self, analysis: QueryAnalysis) -> str:
        if self.config.use_rewritten_question:
            return analysis.rewritten_question

        return analysis.normalized_question

    def _build_search_plan(
        self,
        analysis: QueryAnalysis,
    ) -> list[tuple[SearchStage, dict[str, Any] | None]]:
        plan: list[tuple[SearchStage, dict[str, Any] | None]] = []

        strict_filter = analysis.metadata_filter

        department_filter = None
        if analysis.department_code:
            department_filter = {
                "dept": {"$eq": analysis.department_code}
            }

        content_type_filter = None
        if analysis.content_type:
            content_type_filter = {
                "content_type": {"$eq": analysis.content_type}
            }

        if strict_filter:
            plan.append(("strict_filter", strict_filter))

        if department_filter and department_filter != strict_filter:
            plan.append(("department_only", department_filter))

        if content_type_filter and content_type_filter != strict_filter:
            plan.append(("content_type_only", content_type_filter))

        plan.append(("no_filter", None))

        return plan

    def _search_with_fallback(
        self,
        search_query: str,
        search_plan: list[tuple[SearchStage, dict[str, Any] | None]],
    ) -> tuple[
        list[RetrievedVectorDocument],
        list[SearchAttempt],
        bool,
        list[str],
    ]:
        results: list[RetrievedVectorDocument] = []
        attempts: list[SearchAttempt] = []
        seen_keys: set[str] = set()
        warnings: list[str] = []

        used_fallback = False

        for stage_index, (search_stage, metadata_filter) in enumerate(search_plan):
            if stage_index > 0:
                used_fallback = True

            stage_results = self._search_chroma_once(
                search_query=search_query,
                metadata_filter=metadata_filter,
                search_stage=search_stage,
            )

            attempts.append(
                SearchAttempt(
                    search_stage=search_stage,
                    metadata_filter=metadata_filter,
                    result_count=len(stage_results),
                )
            )

            for item in stage_results:
                key = self._make_document_key(item.document)

                if key in seen_keys:
                    continue

                seen_keys.add(key)
                results.append(item)

                if len(results) >= self.config.search_k:
                    break

            if self._should_stop_search(
                stage_index=stage_index,
                current_result_count=len(results),
            ):
                break

        if used_fallback:
            warnings.append(
                "strict_filter 검색 결과가 부족하여 fallback 검색이 사용되었습니다. "
                "fallback 결과에는 원래 content_type과 다른 문서가 포함될 수 있습니다."
            )

        return results, attempts, used_fallback, warnings

    def _should_stop_search(
        self,
        stage_index: int,
        current_result_count: int,
    ) -> bool:
        if not self.config.use_fallback:
            return True

        if current_result_count >= self.config.search_k:
            return True

        if self.config.fallback_trigger_mode == "only_when_empty":
            if current_result_count > 0:
                return True

            return False

        if self.config.fallback_trigger_mode == "below_min_results":
            if current_result_count >= self.config.min_results_before_fallback:
                return True

            return False

        return False

    def _rerank_results(
        self,
        question: str,
        analysis: QueryAnalysis,
        items: list[RetrievedVectorDocument],
    ) -> list[RetrievedVectorDocument]:
        if self.config.use_lightweight_reranker:
            return self.reranker.rerank(
                question=question,
                analysis=analysis,
                items=items,
            )

        return sorted(
            items,
            key=lambda item: item.score if item.score is not None else float("inf"),
        )

    def _search_chroma_once(
        self,
        search_query: str,
        metadata_filter: dict[str, Any] | None,
        search_stage: SearchStage,
    ) -> list[RetrievedVectorDocument]:
        search_kwargs: dict[str, Any] = {
            "query": search_query,
            "k": self.config.fetch_k,
        }

        if metadata_filter:
            search_kwargs["filter"] = metadata_filter

        raw_results = self.vectorstore.similarity_search_with_score(**search_kwargs)

        return [
            RetrievedVectorDocument(
                document=document,
                score=score,
                search_stage=search_stage,
            )
            for document, score in raw_results
        ]

    def _make_document_key(self, document: Document) -> str:
        metadata = document.metadata

        return str(
            metadata.get("content_hash")
            or metadata.get("original_id")
            or hash(document.page_content)
        )


def run_examples() -> None:
    config = VectorRetrieverConfig(
        search_k=3,
        fetch_k=10,
        min_results_before_fallback=2,
        use_rewritten_question=True,
        use_fallback=True,
        fallback_trigger_mode="only_when_empty",
        use_lightweight_reranker=True,
    )

    retriever = VectorRetriever(config=config)

    example_questions = [
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

    for question in example_questions:
        result = retriever.retrieve(question)

        print("=" * 100)
        print(f"질문: {question}")
        print(result.to_debug_dict())

        if result.documents:
            context = retriever.format_documents_for_context(result.documents)
            print("\n[Context Preview]")
            print(context[:1000])


if __name__ == "__main__":
    run_examples()