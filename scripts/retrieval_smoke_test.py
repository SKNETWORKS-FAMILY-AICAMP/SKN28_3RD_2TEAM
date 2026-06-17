from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import chromadb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from kaist_crawler.retrieval import retrieve_with_metadata_filters, retrieve_without_filters
from kaist_crawler.vector_store import embed_texts


DEFAULT_QUESTIONS = [
    "AI Computing 대학원 입학 정보 알려줘",
    "AI Systems 대학원 입학 지원 조건은?",
    "AX 학과 입시설명회 내용 요약해줘",
    "AI미래학과 교수진은?",
    "KAIST 대학원 장학금이나 등록 관련 정보는?",
    "AI College의 학과와 교육과정 정보를 알려줘",
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run Chroma retrieval smoke tests")
    parser.add_argument("--vector-path", default="data/vector/chroma", help="Chroma vector-store path")
    parser.add_argument("--collection", default=None, help="Chroma collection name")
    parser.add_argument("--top-k", type=int, default=5, help="number of results per query")
    parser.add_argument("--query", action="append", default=[], help="query to test; can be repeated")
    parser.add_argument("--env", default=".env", help="dotenv path with OpenAI settings")
    parser.add_argument(
        "--no-metadata-filter",
        action="store_true",
        help="disable query-based Chroma metadata filter routing",
    )
    args = parser.parse_args()

    load_openai_env(Path(args.env))
    questions = args.query or DEFAULT_QUESTIONS

    client = chromadb.PersistentClient(path=args.vector_path)
    collection_name = args.collection or first_collection_name(client)
    collection = client.get_collection(collection_name)

    query_embeddings, embedding_info = embed_texts(
        questions,
        provider="openai",
        model=os.getenv("OPENAI_EMBEDDING_MODEL"),
        dimensions=None,
        batch_size=16,
    )

    print(
        json.dumps(
            {
                "collection": collection_name,
                "count": collection.count(),
                "embedding": embedding_info,
                "top_k": args.top_k,
                "metadata_filter": not args.no_metadata_filter,
            },
            ensure_ascii=False,
        )
    )
    for index, question in enumerate(questions):
        if args.no_metadata_filter:
            analysis = None
            candidates = retrieve_without_filters(
                collection=collection,
                query_embedding=query_embeddings[index],
                top_k=args.top_k,
            )
        else:
            analysis, candidates = retrieve_with_metadata_filters(
                collection=collection,
                query_embedding=query_embeddings[index],
                question=question,
                top_k=args.top_k,
            )

        question_payload = {"question_index": index + 1, "question": question}
        if analysis is not None:
            question_payload["analysis"] = analysis.to_dict()
        print(json.dumps(question_payload, ensure_ascii=False))
        for rank, candidate in enumerate(candidates, start=1):
            metadata = candidate.metadata
            sample = " ".join(candidate.document.split())[:260]
            print(
                json.dumps(
                    {
                        "rank": rank,
                        "distance": round(float(candidate.distance), 4),
                        "stage": candidate.stage,
                        "where": candidate.where,
                        "site": metadata.get("site"),
                        "document_type": metadata.get("document_type"),
                        "content_type": metadata.get("content_type"),
                        "source_type": metadata.get("source_type"),
                        "dept": metadata.get("dept"),
                        "dept_name": metadata.get("dept_name"),
                        "section": metadata.get("section"),
                        "page": metadata.get("page"),
                        "title": metadata.get("title"),
                        "url": metadata.get("source_url"),
                        "chunk_id": candidate.chunk_id,
                        "sample": sample,
                    },
                    ensure_ascii=False,
                )
            )
    return 0


def load_openai_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in {"OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_EMBEDDING_MODEL"}:
            os.environ[key] = value


def first_collection_name(client: chromadb.PersistentClient) -> str:
    collections = client.list_collections()
    if not collections:
        raise RuntimeError("No Chroma collections found")
    return getattr(collections[0], "name", str(collections[0]))


if __name__ == "__main__":
    raise SystemExit(main())
