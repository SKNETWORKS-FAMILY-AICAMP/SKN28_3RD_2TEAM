from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import build_vectors_from_chunks, run_crawl, run_raw_crawl
from .vector_store import DEFAULT_OPENAI_EMBEDDING_MODEL


def add_embedding_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--embedding-provider",
        choices=["hash", "openai"],
        default="hash",
        help="embedding provider for vector build",
    )
    parser.add_argument(
        "--embedding-model",
        default=None,
        help=f"embedding model; OpenAI default is {DEFAULT_OPENAI_EMBEDDING_MODEL}",
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=None,
        help="optional embedding dimensions parameter",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=64,
        help="number of chunks per embedding request",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Chroma collection name; default is derived from provider/model/dimensions",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KAIST College of AI crawler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="collect raw data, extract text, chunk, and build vectors")
    run.add_argument("--config", default="configs/kaist_ai_sources.yml", help="source YAML config")
    run.add_argument("--output", default="data", help="output data directory")
    run.add_argument("--source", action="append", default=[], help="source id to crawl; can be repeated")
    run.add_argument("--skip-vector", action="store_true", help="skip vector-store build")
    add_embedding_args(run)

    raw = subparsers.add_parser("raw", help="collect raw data only")
    raw.add_argument("--config", default="configs/kaist_ai_sources.yml", help="source YAML config")
    raw.add_argument("--output", default="data", help="output data directory")
    raw.add_argument("--source", action="append", default=[], help="source id to crawl; can be repeated")

    build = subparsers.add_parser("build-vector", help="build vector store from processed chunks")
    build.add_argument("--input", default="data/processed/chunks.jsonl", help="chunks JSONL path")
    build.add_argument("--output", default="data", help="output data directory")
    add_embedding_args(build)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        selected = set(args.source) if args.source else None
        documents, chunks = run_crawl(
            config_path=args.config,
            output_root=args.output,
            source_ids=selected,
            build_vectors=not args.skip_vector,
            embedding_provider=args.embedding_provider,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
            embedding_batch_size=args.embedding_batch_size,
            collection_name=args.collection,
        )
        print(f"documents={len(documents)} chunks={len(chunks)} output={Path(args.output).resolve()}")
        return 0
    if args.command == "raw":
        selected = set(args.source) if args.source else None
        document_count, errors = run_raw_crawl(
            config_path=args.config,
            output_root=args.output,
            source_ids=selected,
        )
        for error in errors:
            print(json.dumps(error, ensure_ascii=False))
        print(f"raw_documents_seen={document_count} errors={len(errors)} output={Path(args.output, 'raw').resolve()}")
        return 0
    if args.command == "build-vector":
        count = build_vectors_from_chunks(
            args.input,
            args.output,
            embedding_provider=args.embedding_provider,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
            embedding_batch_size=args.embedding_batch_size,
            collection_name=args.collection,
        )
        print(f"chunks={count} vector_output={Path(args.output, 'vector').resolve()}")
        return 0
    parser.error("unknown command")
    return 2
