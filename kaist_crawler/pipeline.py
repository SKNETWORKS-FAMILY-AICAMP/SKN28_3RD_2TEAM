from __future__ import annotations

import json
import shutil
from pathlib import Path

from .adapters import create_adapter
from .config import load_crawler_config, load_sources
from .http_client import HttpClient
from .models import Chunk, Document, SourceConfig
from .processor import process_raw_documents
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
    clean: bool = False,
) -> tuple[list[Document], list[Chunk]]:
    crawler_config = load_crawler_config(config_path, source_ids)
    sources = crawler_config.sources
    output_root = Path(output_root)
    if clean:
        clean_output(output_root, targets=("raw", "processed", "vector"))

    _, crawl_errors = crawl_sources_raw(
        sources=sources,
        output_root=output_root,
        request_timeout_seconds=crawler_config.request_timeout_seconds,
        polite_delay_seconds=crawler_config.polite_delay_seconds,
    )
    documents, chunks, _process_errors, _ = process_raw_data_from_sources(
        sources=sources,
        output_root=output_root,
        clean=False,
        extra_errors=crawl_errors,
    )
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
    clean: bool = False,
) -> tuple[int, list[dict]]:
    crawler_config = load_crawler_config(config_path, source_ids)
    output_root = Path(output_root)
    if clean:
        clean_output(output_root, targets=("raw",))
    return crawl_sources_raw(
        sources=crawler_config.sources,
        output_root=output_root,
        request_timeout_seconds=crawler_config.request_timeout_seconds,
        polite_delay_seconds=crawler_config.polite_delay_seconds,
    )


def process_raw_data(
    *,
    config_path: str | Path,
    output_root: str | Path,
    source_ids: set[str] | None = None,
    clean: bool = False,
) -> tuple[list[Document], list[Chunk], list[dict], list[dict]]:
    sources = load_sources(config_path, source_ids)
    return process_raw_data_from_sources(sources=sources, output_root=output_root, clean=clean)


def crawl_sources_raw(
    *,
    sources: list[SourceConfig],
    output_root: str | Path,
    request_timeout_seconds: int = 30,
    polite_delay_seconds: float = 0.0,
) -> tuple[int, list[dict]]:
    client = HttpClient(timeout_seconds=request_timeout_seconds, delay_seconds=polite_delay_seconds)
    store = RawStore(output_root)
    errors: list[dict] = []
    try:
        for source in sources:
            adapter = create_adapter(source, client, store)
            adapter.crawl()
            errors.extend(adapter.errors)
    finally:
        raw_file_count = store.saved_count
        store.close()
    return raw_file_count, errors


def process_raw_data_from_sources(
    *,
    sources: list[SourceConfig],
    output_root: str | Path,
    clean: bool = False,
    extra_errors: list[dict] | None = None,
) -> tuple[list[Document], list[Chunk], list[dict], list[dict]]:
    output_root = Path(output_root)
    if clean:
        clean_output(output_root, targets=("processed",))
    processed_root = output_root / "processed"
    processed_root.mkdir(parents=True, exist_ok=True)
    documents, chunks, errors, filtered = process_raw_documents(output_root=output_root, sources=sources)
    all_errors = list(extra_errors or [])
    all_errors.extend(errors)
    write_jsonl(processed_root / "documents.jsonl", [doc.to_dict() for doc in documents])
    write_jsonl(processed_root / "chunks.jsonl", [chunk.to_dict() for chunk in chunks])
    write_jsonl(processed_root / "errors.jsonl", all_errors)
    write_jsonl(processed_root / "filtered.jsonl", filtered)
    return documents, chunks, all_errors, filtered


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


def clean_output(output_root: str | Path, *, targets: tuple[str, ...]) -> None:
    root = Path(output_root)
    for target in targets:
        path = root / target
        if path.exists():
            shutil.rmtree(path)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
