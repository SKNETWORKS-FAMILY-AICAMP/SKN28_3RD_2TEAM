from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from .pipeline import (
    build_quality_gate_from_processed,
    build_vectors_from_chunks,
    process_raw_data,
    run_crawl,
    run_raw_crawl,
)
from .site_analyzer import analysis_to_json, analysis_to_yaml, analyze_site
from .rag_relevance import DEFAULT_LLM_RELEVANCE_MODEL
from .vector_store import DEFAULT_OPENAI_EMBEDDING_MODEL


DEFAULT_CONFIG = "configs/kaist_sources.yml"
DEFAULT_OUTPUT = "data/kaist"
DEFAULT_CHUNKS_INPUT = "data/kaist/processed/chunks.jsonl"


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


def add_relevance_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--use-llm-relevance",
        action="store_true",
        help="use LLM only for ambiguous document relevance decisions",
    )
    parser.add_argument(
        "--relevance-model",
        default=None,
        help=f"LLM relevance model; default is {DEFAULT_LLM_RELEVANCE_MODEL}",
    )
    parser.add_argument(
        "--max-llm-relevance",
        type=int,
        default=None,
        help="maximum ambiguous documents to send to LLM relevance classifier",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Graduate school RAG crawler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="collect raw data, extract text, chunk, and build vectors")
    run.add_argument("--config", default=DEFAULT_CONFIG, help="source YAML config")
    run.add_argument("--output", default=DEFAULT_OUTPUT, help="output data directory")
    run.add_argument("--source", action="append", default=[], help="source id to crawl; can be repeated")
    run.add_argument("--skip-vector", action="store_true", help="skip vector-store build")
    run.add_argument("--clean", action="store_true", help="delete raw, processed, and vector output before running")
    run.add_argument(
        "--include-non-candidates",
        action="store_true",
        help="include chunks marked vector_candidate=false in vector store",
    )
    add_relevance_args(run)
    add_embedding_args(run)

    raw = subparsers.add_parser("raw", help="collect raw data only")
    raw.add_argument("--config", default=DEFAULT_CONFIG, help="source YAML config")
    raw.add_argument("--output", default=DEFAULT_OUTPUT, help="output data directory")
    raw.add_argument("--source", action="append", default=[], help="source id to crawl; can be repeated")
    raw.add_argument("--clean", action="store_true", help="delete raw output before crawling")

    process = subparsers.add_parser("process", help="extract documents and chunks from existing raw data")
    process.add_argument("--config", default=DEFAULT_CONFIG, help="source YAML config")
    process.add_argument("--output", default=DEFAULT_OUTPUT, help="output data directory")
    process.add_argument("--source", action="append", default=[], help="source id to process; can be repeated")
    process.add_argument("--clean", action="store_true", help="delete processed output before processing")
    add_relevance_args(process)

    build = subparsers.add_parser("build-vector", help="build vector store from processed chunks")
    build.add_argument("--input", default=DEFAULT_CHUNKS_INPUT, help="chunks JSONL path")
    build.add_argument("--output", default=DEFAULT_OUTPUT, help="output data directory")
    build.add_argument(
        "--include-non-candidates",
        action="store_true",
        help="include chunks marked vector_candidate=false in vector store",
    )
    add_embedding_args(build)

    analyze = subparsers.add_parser("analyze-site", help="analyze a school site and recommend a source config")
    analyze.add_argument("url", help="graduate school site URL to analyze")
    analyze.add_argument("--id", default=None, help="source id to use in the recommended config")
    analyze.add_argument("--name", default=None, help="source name to use in the recommended config")
    analyze.add_argument("--format", choices=["yaml", "json"], default="yaml", help="output format")
    analyze.add_argument("--output", default=None, help="optional path to write the analysis result")
    analyze.add_argument("--max-routes", type=int, default=24, help="maximum recommended routes")
    analyze.add_argument("--max-assets", type=int, default=5, help="maximum JS/CSS assets to inspect")
    analyze.add_argument("--no-fetch-assets", action="store_true", help="skip JS/CSS asset inspection")

    quality = subparsers.add_parser("quality-gate", help="evaluate processed documents/chunks before vector storage")
    quality.add_argument("--config", default=DEFAULT_CONFIG, help="optional source YAML config")
    quality.add_argument("--output", default=DEFAULT_OUTPUT, help="output data directory containing processed JSONL files")
    quality.add_argument("--source", action="append", default=[], help="source id to evaluate; can be repeated")

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
            include_non_candidates=args.include_non_candidates,
            use_llm_relevance=args.use_llm_relevance,
            relevance_model=args.relevance_model,
            max_llm_relevance=args.max_llm_relevance,
            clean=args.clean,
        )
        print(f"documents={len(documents)} chunks={len(chunks)} output={Path(args.output).resolve()}")
        return 0
    if args.command == "raw":
        selected = set(args.source) if args.source else None
        raw_file_count, errors = run_raw_crawl(
            config_path=args.config,
            output_root=args.output,
            source_ids=selected,
            clean=args.clean,
        )
        for error in errors:
            print(json.dumps(error, ensure_ascii=False))
        print(f"raw_files_written={raw_file_count} errors={len(errors)} output={Path(args.output, 'raw').resolve()}")
        return 0
    if args.command == "process":
        selected = set(args.source) if args.source else None
        documents, chunks, errors, filtered = process_raw_data(
            config_path=args.config,
            output_root=args.output,
            source_ids=selected,
            clean=args.clean,
            use_llm_relevance=args.use_llm_relevance,
            relevance_model=args.relevance_model,
            max_llm_relevance=args.max_llm_relevance,
        )
        for error in errors:
            print(json.dumps(error, ensure_ascii=False))
        relevance_sources = collections.Counter(
            str(doc.metadata.get("relevance_source") or "missing") for doc in documents
        )
        vector_candidates = sum(1 for chunk in chunks if chunk.metadata.get("vector_candidate", True) is not False)
        print(
            f"documents={len(documents)} chunks={len(chunks)} "
            f"vector_candidates={vector_candidates} errors={len(errors)} filtered={len(filtered)} "
            f"relevance_sources={dict(relevance_sources)} output={Path(args.output, 'processed').resolve()}"
        )
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
            include_non_candidates=args.include_non_candidates,
        )
        print(f"chunks={count} vector_output={Path(args.output, 'vector').resolve()}")
        return 0
    if args.command == "analyze-site":
        analysis = analyze_site(
            args.url,
            source_id=args.id,
            name=args.name,
            max_routes=args.max_routes,
            max_assets=args.max_assets,
            fetch_assets=not args.no_fetch_assets,
        )
        output = analysis_to_json(analysis) if args.format == "json" else analysis_to_yaml(analysis)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="utf-8")
            print(f"analysis_output={output_path.resolve()}")
        else:
            print(output)
        return 0
    if args.command == "quality-gate":
        selected = set(args.source) if args.source else None
        report = build_quality_gate_from_processed(
            output_root=args.output,
            config_path=args.config,
            source_ids=selected,
        )
        print(
            f"quality_status={report['status']} score={report['score']} "
            f"output={Path(args.output, 'processed').resolve()}"
        )
        return 0
    parser.error("unknown command")
    return 2
