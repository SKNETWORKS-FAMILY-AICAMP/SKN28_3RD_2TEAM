"""
build_vectorstore.py

전처리된 JSONL(vector_documents.jsonl)을 읽어서
KAIST AI College RAG용 Chroma vectorstore를 생성하는 스크립트입니다.

역할:
- JSONL 로드
- text 정리
- metadata 정규화
- 검색 효율을 위한 page_content 헤더 추가
- 낮은 가치 문서 attachment_meta 기본 제외
- 중복 문서 제거
- Chroma vectorstore 저장
- content_type/source_type/학과별 문서 분포 출력
- 실패 질문 중심 smoke test 실행

실행 예시:
    python data/build_vectorstore.py --reset --smoke-test

권장 실행:
    python data/build_vectorstore.py --reset --drop-low-value-docs --smoke-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
from tqdm import tqdm

if TYPE_CHECKING:
    from langchain_chroma import Chroma
    from langchain_core.documents import Document


# ============================================================
# 1. 기본 설정
# ============================================================

CURRENT_FILE = Path(__file__).resolve()
DEFAULT_PROJECT_ROOT = CURRENT_FILE.parents[1]

DEFAULT_JSONL_REL_PATH = (
    Path("data") / "processed" / "json" / "vector_documents.jsonl"
)

DEFAULT_CHROMA_REL_DIR = (
    Path("data") / "vectorstore" / "chroma_db"
)

DEFAULT_COLLECTION_NAME = "kaist_graduate_info"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_BATCH_SIZE = 100


# ============================================================
# 2. 텍스트 / metadata 정리 함수
# ============================================================

def clean_text(text: str) -> str:
    """
    JSONL의 text 필드를 RAG 저장에 적합하게 정리합니다.
    문장 내용은 바꾸지 않고 공백만 정리합니다.
    """
    if not isinstance(text, str):
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def safe_metadata_value(value: Any) -> Any:
    """
    Chroma metadata에 안전하게 넣을 수 있는 값으로 변환합니다.

    Chroma metadata는 문자열, 숫자, bool 같은 단순 타입이 안전합니다.
    - None: 제거
    - list/dict: JSON 문자열로 변환
    - 그 외 타입: str로 변환
    """
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def normalize_metadata(raw_metadata: dict[str, Any] | None) -> dict[str, Any]:
    """
    원본 metadata를 Chroma 저장에 적합하게 정규화합니다.

    추가 alias:
    - dept_name -> department
    - dept -> department_code
    - content_type -> doc_type
    - source_url/url -> source
    """
    metadata: dict[str, Any] = {}

    if not isinstance(raw_metadata, dict):
        raw_metadata = {}

    for key, value in raw_metadata.items():
        safe_value = safe_metadata_value(value)

        if safe_value is not None:
            metadata[key] = safe_value

    if "dept_name" in metadata:
        metadata["department"] = metadata["dept_name"]

    if "dept" in metadata:
        metadata["department_code"] = metadata["dept"]

    if "content_type" in metadata:
        metadata["doc_type"] = metadata["content_type"]

    if "source_url" in metadata:
        metadata["source"] = metadata["source_url"]
    elif "url" in metadata:
        metadata["source"] = metadata["url"]
    elif "source" not in metadata:
        metadata["source"] = "unknown"

    return metadata


# ============================================================
# 3. RAG 검색 효율 향상용 page_content 생성
# ============================================================

def build_rag_page_content(text: str, metadata: dict[str, Any]) -> str:
    """
    벡터 검색 효율을 높이기 위해 핵심 metadata를 본문 앞에 짧게 붙입니다.

    이유:
    - metadata는 필터링과 출처 표시에 좋지만, 일반 벡터 유사도 검색에는 직접 반영되지 않습니다.
    - 학과명, 문서유형, 제목, 과목코드, 이름, 이메일, 전화번호 같은 값은
      사용자의 질문과 직접 매칭될 가능성이 높으므로 page_content에도 포함합니다.
    """
    keyword_parts: list[str] = []

    field_map = [
        ("dept_name", "학과"),
        ("dept", "학과코드"),
        ("content_type", "문서유형"),
        ("source_type", "데이터출처유형"),
        ("title", "제목"),
        ("section", "섹션"),
        ("admission_type", "입학항목"),
        ("schedule_date", "일정"),
        ("course_code", "과목코드"),
        ("course_code_norm", "정규화 과목코드"),
        ("course_level", "과목수준"),
        ("course_type", "이수구분"),
        ("tracks", "관련트랙"),
        ("name", "이름"),
        ("role", "역할"),
        ("email", "이메일"),
        ("phone", "전화번호"),
        ("website", "웹사이트"),
        ("homepage", "홈페이지"),
        ("event_date", "행사일"),
        ("file_name", "파일명"),
        ("page", "페이지"),
        ("url", "URL"),
        ("source_url", "출처URL"),
    ]

    for key, label in field_map:
        value = metadata.get(key)

        if value:
            keyword_parts.append(f"{label}: {value}")

    if not keyword_parts:
        return text

    keyword_header = "\n".join(keyword_parts)

    return f"[검색 키워드]\n{keyword_header}\n\n[문서 내용]\n{text}"


# ============================================================
# 4. ID / hash 함수
# ============================================================

def make_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_hash_id(text: str, metadata: dict[str, Any]) -> str:
    """
    원본 id가 없거나 중복될 때 사용할 안정적인 hash id를 생성합니다.
    """
    base = "|".join(
        [
            str(metadata.get("dept_name", "")),
            str(metadata.get("dept", "")),
            str(metadata.get("content_type", "")),
            str(metadata.get("source_type", "")),
            str(metadata.get("title", "")),
            str(metadata.get("section", "")),
            str(metadata.get("page", "")),
            text,
        ]
    )

    return hashlib.sha256(base.encode("utf-8")).hexdigest()


# ============================================================
# 5. JSONL 로드 -> Document 변환
# ============================================================

def load_documents_from_jsonl(
    jsonl_path: Path,
    drop_low_value_docs: bool = True,
) -> tuple[list[Document], list[str]]:
    """
    vector_documents.jsonl을 읽어서 LangChain Document 리스트와 id 리스트로 변환합니다.

    JSONL 예상 구조:
        {
          "id": "...",
          "text": "...",
          "metadata": {...}
        }
    """
    from langchain_core.documents import Document

    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL 파일을 찾을 수 없습니다: {jsonl_path}")

    low_value_content_types = {
        "attachment_meta",
    }

    documents: list[Document] = []
    ids: list[str] = []

    seen_ids: set[str] = set()
    seen_text_hashes: set[str] = set()

    parse_errors: list[tuple[int, str]] = []
    skipped_empty_text = 0
    skipped_low_value = 0
    skipped_duplicate_text = 0
    skipped_duplicate_id_fixed = 0

    content_type_counter: Counter[str] = Counter()
    source_type_counter: Counter[str] = Counter()
    dept_counter: Counter[str] = Counter()

    with jsonl_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    for line_no, line in enumerate(tqdm(lines, desc="JSONL 로드 중"), start=1):
        line = line.strip()

        if not line:
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            parse_errors.append((line_no, str(e)))
            continue

        text = clean_text(obj.get("text", ""))

        if not text:
            skipped_empty_text += 1
            continue

        metadata = normalize_metadata(obj.get("metadata", {}))

        content_type = str(metadata.get("content_type", "unknown"))
        source_type = str(metadata.get("source_type", "unknown"))
        dept_label = str(
            metadata.get("dept_name")
            or metadata.get("dept")
            or "unknown"
        )

        content_type_counter[content_type] += 1
        source_type_counter[source_type] += 1
        dept_counter[dept_label] += 1

        if drop_low_value_docs and content_type in low_value_content_types:
            skipped_low_value += 1
            continue

        page_content = build_rag_page_content(
            text=text,
            metadata=metadata,
        )

        text_hash = make_text_hash(page_content)

        if text_hash in seen_text_hashes:
            skipped_duplicate_text += 1
            continue

        seen_text_hashes.add(text_hash)

        doc_id = obj.get("id")

        if not doc_id:
            doc_id = make_hash_id(page_content, metadata)

        doc_id = str(doc_id)

        if doc_id in seen_ids:
            doc_id = make_hash_id(page_content, metadata)
            skipped_duplicate_id_fixed += 1

        seen_ids.add(doc_id)

        metadata["original_id"] = str(obj.get("id", doc_id))
        metadata["content_hash"] = text_hash
        metadata["char_len"] = len(page_content)

        documents.append(
            Document(
                page_content=page_content,
                metadata=metadata,
            )
        )
        ids.append(doc_id)

    print("\n[JSONL 로드 결과]")
    print(f"- JSONL 경로: {jsonl_path}")
    print(f"- 전체 라인 수: {len(lines)}")
    print(f"- 변환된 문서 수: {len(documents)}")
    print(f"- 파싱 오류 수: {len(parse_errors)}")
    print(f"- 빈 text 제외 수: {skipped_empty_text}")
    print(f"- 낮은 가치 문서 제외 수: {skipped_low_value}")
    print(f"- 중복 text 제외 수: {skipped_duplicate_text}")
    print(f"- 중복 id hash 재생성 수: {skipped_duplicate_id_fixed}")

    if content_type_counter:
        print("\n[content_type 분포 - 원본 JSONL 기준]")
        for content_type_name, count in content_type_counter.most_common():
            print(f"- {content_type_name}: {count}")

    if source_type_counter:
        print("\n[source_type 분포 - 원본 JSONL 기준]")
        for source_type_name, count in source_type_counter.most_common():
            print(f"- {source_type_name}: {count}")

    if dept_counter:
        print("\n[학과별 문서 분포 - 원본 JSONL 기준]")
        for dept_name, count in dept_counter.most_common():
            print(f"- {dept_name}: {count}")

    if parse_errors:
        print("\n[파싱 오류 예시]")
        for line_no, error_message in parse_errors[:5]:
            print(f"- line {line_no}: {error_message}")

    if not documents:
        raise ValueError(
            "저장할 문서가 없습니다. JSONL 파일 내용 또는 drop_low_value_docs 옵션을 확인하세요."
        )

    return documents, ids


# ============================================================
# 6. Chroma vectorstore 생성
# ============================================================

def build_chroma_vectorstore(
    jsonl_path: Path,
    chroma_dir: Path,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    reset: bool = True,
    drop_low_value_docs: bool = True,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Chroma:
    """
    JSONL 파일로부터 Chroma vectorstore를 생성합니다.
    """
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    if reset and chroma_dir.exists():
        print(f"[초기화] 기존 Chroma DB 삭제: {chroma_dir}")
        shutil.rmtree(chroma_dir)

    chroma_dir.mkdir(parents=True, exist_ok=True)

    documents, ids = load_documents_from_jsonl(
        jsonl_path=jsonl_path,
        drop_low_value_docs=drop_low_value_docs,
    )

    embedding_model = OpenAIEmbeddings(
        model=embedding_model_name,
    )

    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embedding_model,
        persist_directory=str(chroma_dir),
    )

    for start in tqdm(range(0, len(documents), batch_size), desc="Chroma 인덱싱 중"):
        end = start + batch_size

        batch_documents = documents[start:end]
        batch_ids = ids[start:end]

        vector_store.add_documents(
            documents=batch_documents,
            ids=batch_ids,
        )

    print("\n[Chroma 저장 완료]")
    print(f"- 저장 위치: {chroma_dir}")
    print(f"- collection_name: {collection_name}")
    print(f"- embedding_model: {embedding_model_name}")
    print(f"- 저장 문서 수: {len(documents)}")

    return vector_store


# ============================================================
# 7. 저장된 Chroma vectorstore 로드
# ============================================================

def load_chroma_vectorstore(
    chroma_dir: Path,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> Chroma:
    """
    저장된 Chroma vectorstore를 다시 불러옵니다.
    RAG 코드에서 이 함수만 import해서 사용할 수 있습니다.
    """
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    embedding_model = OpenAIEmbeddings(
        model=embedding_model_name,
    )

    return Chroma(
        collection_name=collection_name,
        embedding_function=embedding_model,
        persist_directory=str(chroma_dir),
    )


# ============================================================
# 8. vectorstore 저장 확인용 smoke test
# ============================================================

def run_smoke_test(vector_store: Chroma) -> None:
    """
    vectorstore 생성 후 저장이 정상인지 확인하기 위한 검색 테스트입니다.

    이전 평가에서 문제가 된 질문 유형을 포함합니다.
    """
    test_queries = [
        "AI컴퓨팅학과 석사 지원 자격",
        "AX학과 교수 이메일",
        "KAIST 학과사무실 전화번호",
        "AI미래학과는 어떤 인재를 양성하려고 해?",
        "AI컴퓨팅학과와 AX학과를 비교해줘.",
        "AI컴퓨팅학과의 연락처가 문서에 나와 있어?",
        "AI대학 학과별 홈페이지 URL을 정리해줘.",
        "산업 현장에 AI를 적용하고 싶은데 어떤 학과가 적합해?",
        "AI시스템학과의 교육과정을 알려줘.",
    ]

    print("\n[간단 검색 테스트]")

    for query in test_queries:
        print("=" * 100)
        print(f"질문: {query}")

        results = vector_store.similarity_search_with_score(
            query,
            k=3,
        )

        if not results:
            print("- 검색 결과 없음")
            continue

        for idx, (doc, score) in enumerate(results, start=1):
            metadata = doc.metadata

            print("-" * 100)
            print(f"[결과 {idx}] score={score}")
            print(
                {
                    "dept": metadata.get("dept"),
                    "dept_name": metadata.get("dept_name"),
                    "source_type": metadata.get("source_type"),
                    "content_type": metadata.get("content_type"),
                    "title": metadata.get("title"),
                    "source": metadata.get("source") or metadata.get("source_url"),
                }
            )
            print(doc.page_content[:700])


# ============================================================
# 9. 경로 처리
# ============================================================

def resolve_path(path: Path, project_root: Path) -> Path:
    """
    CLI에서 받은 경로를 안정적인 절대경로로 변환합니다.

    - 절대경로면 그대로 사용
    - 상대경로면 project_root 기준으로 변환
    """
    if path.is_absolute():
        return path

    return project_root / path


# ============================================================
# 10. CLI
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="전처리 JSONL 파일로 Chroma vectorstore를 생성합니다."
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help="프로젝트 루트 경로",
    )

    parser.add_argument(
        "--jsonl-path",
        type=Path,
        default=None,
        help=(
            "vector_documents.jsonl 파일 경로. "
            "생략하면 project-root/data/processed/json/vector_documents.jsonl 사용"
        ),
    )

    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=None,
        help=(
            "Chroma DB 저장 폴더. "
            "생략하면 project-root/data/vectorstore/chroma_db 사용"
        ),
    )

    parser.add_argument(
        "--collection-name",
        type=str,
        default=DEFAULT_COLLECTION_NAME,
        help="Chroma collection 이름",
    )

    parser.add_argument(
        "--embedding-model",
        type=str,
        default=DEFAULT_EMBEDDING_MODEL,
        help="OpenAI embedding model 이름",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Chroma add_documents 배치 크기",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="기존 Chroma DB를 삭제하고 새로 생성",
    )

    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="기존 Chroma DB를 유지하고 추가 저장",
    )

    parser.add_argument(
        "--drop-low-value-docs",
        action="store_true",
        help="attachment_meta 등 검색 가치가 낮은 문서를 제외합니다. 기본값도 제외입니다.",
    )

    parser.add_argument(
        "--keep-low-value-docs",
        action="store_true",
        help="attachment_meta 같은 낮은 가치 문서도 vectorstore에 포함합니다.",
    )

    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="저장 후 similarity_search 테스트 실행",
    )

    return parser.parse_args()


def main() -> None:
    load_dotenv()

    args = parse_args()

    project_root: Path = args.project_root.resolve()

    jsonl_path: Path = resolve_path(
        args.jsonl_path or DEFAULT_JSONL_REL_PATH,
        project_root,
    )

    chroma_dir: Path = resolve_path(
        args.chroma_dir or DEFAULT_CHROMA_REL_DIR,
        project_root,
    )

    # 기본 동작은 reset=True.
    # --no-reset을 명시한 경우만 기존 DB에 추가 저장.
    reset = not args.no_reset

    if args.reset:
        reset = True

    # 기본적으로 낮은 가치 문서는 제외.
    # --keep-low-value-docs를 명시한 경우만 포함.
    drop_low_value_docs = True

    if args.drop_low_value_docs:
        drop_low_value_docs = True

    if args.keep_low_value_docs:
        drop_low_value_docs = False

    print("[설정]")
    print(f"- project_root: {project_root}")
    print(f"- jsonl_path: {jsonl_path}")
    print(f"- chroma_dir: {chroma_dir}")
    print(f"- collection_name: {args.collection_name}")
    print(f"- embedding_model: {args.embedding_model}")
    print(f"- batch_size: {args.batch_size}")
    print(f"- reset: {reset}")
    print(f"- drop_low_value_docs: {drop_low_value_docs}")

    vector_store = build_chroma_vectorstore(
        jsonl_path=jsonl_path,
        chroma_dir=chroma_dir,
        collection_name=args.collection_name,
        embedding_model_name=args.embedding_model,
        reset=reset,
        drop_low_value_docs=drop_low_value_docs,
        batch_size=args.batch_size,
    )

    if args.smoke_test:
        run_smoke_test(vector_store)


if __name__ == "__main__":
    main()