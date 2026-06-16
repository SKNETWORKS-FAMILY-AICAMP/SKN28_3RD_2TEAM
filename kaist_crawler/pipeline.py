from __future__ import annotations

import json
from pathlib import Path

from .adapters import create_adapter
from .config import load_sources
from .extractors import chunk_documents
from .http_client import HttpClient
from .models import Chunk, Document
from .store import RawStore
from .vector_store import build_vector_store


def run_crawl(
    *,
    config_path: str | Path,
    output_root: str | Path,
    source_ids: set[str] | None = None,
    build_vectors: bool = True,
    embedding_provider: str = "hash",
    embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
    embedding_batch_size: int = 64,
    collection_name: str | None = None,
) -> tuple[list[Document], list[Chunk]]:
    sources = load_sources(config_path, source_ids)
    output_root = Path(output_root)
    processed_root = output_root / "processed"
    processed_root.mkdir(parents=True, exist_ok=True)

    client = HttpClient()
    store = RawStore(output_root)
    documents: list[Document] = []
    errors: list[dict] = []
    try:
        for source in sources:
            adapter = create_adapter(source, client, store)
            documents.extend(adapter.crawl())
            errors.extend(adapter.errors)
    finally:
        store.close()

    chunks = chunk_documents(documents)
    write_jsonl(processed_root / "documents.jsonl", [doc.to_dict() for doc in documents])
    write_jsonl(processed_root / "chunks.jsonl", [chunk.to_dict() for chunk in chunks])
    write_jsonl(processed_root / "errors.jsonl", errors)
    if build_vectors:
        build_vector_store(
            chunks,
            output_root,
            collection_name=collection_name,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            embedding_batch_size=embedding_batch_size,
        )
    return documents, chunks


def run_raw_crawl(
    *,
    config_path: str | Path,
    output_root: str | Path,
    source_ids: set[str] | None = None,
) -> tuple[int, list[dict]]:
    sources = load_sources(config_path, source_ids)
    client = HttpClient()
    store = RawStore(output_root)
    document_count = 0
    errors: list[dict] = []
    try:
        for source in sources:
            adapter = create_adapter(source, client, store)
            documents = adapter.crawl()
            document_count += len(documents)
            errors.extend(adapter.errors)
    finally:
        store.close()
    return document_count, errors


def build_vectors_from_chunks(
    input_path: str | Path,
    output_root: str | Path,
    *,
    embedding_provider: str = "hash",
    embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
    embedding_batch_size: int = 64,
    collection_name: str | None = None,
) -> int:
    chunks = []
    with Path(input_path).open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            chunks.append(
                Chunk(
                    chunk_id=data["chunk_id"],
                    doc_id=data["doc_id"],
                    site=data["site"],
                    source_url=data["source_url"],
                    text=data["text"],
                    chunk_index=data["chunk_index"],
                    metadata=data.get("metadata", {}),
                )
            )
    build_vector_store(
        chunks,
        output_root,
        collection_name=collection_name,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        embedding_batch_size=embedding_batch_size,
    )
    return len(chunks)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
