from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .models import Chunk, Document, SourceConfig


@dataclass(frozen=True)
class SiteQuality:
    site: str
    status: str
    score: int
    document_count: int
    chunk_count: int
    error_count: int
    filtered_count: int
    warnings: list[str] = field(default_factory=list)
    counters: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualityGateReport:
    status: str
    score: int
    summary: dict[str, Any]
    warnings: list[str]
    sites: list[SiteQuality]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sites"] = [site.to_dict() for site in self.sites]
        return payload


def build_quality_gate_report(
    *,
    documents: list[Document],
    chunks: list[Chunk],
    errors: list[dict],
    filtered: list[dict],
    sources: list[SourceConfig] | None = None,
) -> QualityGateReport:
    source_ids = [source.id for source in sources] if sources else sorted({doc.site for doc in documents} | {chunk.site for chunk in chunks})
    sites = [
        build_site_quality(
            site=site,
            documents=[doc for doc in documents if doc.site == site],
            chunks=[chunk for chunk in chunks if chunk.site == site],
            errors=[error for error in errors if error.get("site") == site],
            filtered=[event for event in filtered if event.get("site") == site],
        )
        for site in source_ids
    ]
    warnings: list[str] = []
    if not chunks:
        warnings.append("No chunks were produced.")
    if any(site.status == "fail" for site in sites):
        warnings.append("At least one site failed the quality gate.")
    if sum(1 for chunk in chunks if not chunk.metadata.get("dept")):
        warnings.append("Some chunks are missing dept metadata.")
    candidate_chunks = [chunk for chunk in chunks if chunk.metadata.get("vector_candidate", True) is not False]
    if chunks and not candidate_chunks:
        warnings.append("No chunks are marked as vector candidates.")

    score = min((site.score for site in sites), default=0)
    status = status_from_score(score)
    if any(site.status == "fail" for site in sites):
        status = "fail"
    elif any(site.status == "warn" for site in sites) and status == "pass":
        status = "warn"

    summary = {
        "documents": len(documents),
        "chunks": len(chunks),
        "vector_candidate_chunks": len(candidate_chunks),
        "errors": len(errors),
        "filtered": len(filtered),
        "institution": dict(counter_from_metadata(chunks, "institution")),
        "college": dict(counter_from_metadata(chunks, "college")),
        "source_type": dict(counter_from_metadata(chunks, "source_type")),
        "content_type": dict(counter_from_metadata(chunks, "content_type")),
        "dept": dict(counter_from_metadata(chunks, "dept")),
    }
    return QualityGateReport(status=status, score=score, summary=summary, warnings=warnings, sites=sites)


def build_site_quality(
    *,
    site: str,
    documents: list[Document],
    chunks: list[Chunk],
    errors: list[dict],
    filtered: list[dict],
) -> SiteQuality:
    warnings: list[str] = []
    score = 100
    if not chunks:
        warnings.append("No chunks were produced for this site.")
        score -= 70
    missing_dept = sum(1 for chunk in chunks if not chunk.metadata.get("dept"))
    if chunks and missing_dept:
        warnings.append(f"{missing_dept} chunk(s) are missing dept metadata.")
        score -= 30
    general_ratio = ratio(sum(1 for chunk in chunks if chunk.metadata.get("content_type") == "general"), len(chunks))
    if general_ratio > 0.35:
        warnings.append(f"general content ratio is high ({general_ratio:.0%}).")
        score -= 15
    pdf_ratio = ratio(sum(1 for chunk in chunks if chunk.metadata.get("source_type") == "pdf"), len(chunks))
    if pdf_ratio > 0.70:
        warnings.append(f"PDF chunk ratio is high ({pdf_ratio:.0%}); review low-value PDFs before vector storage.")
        score -= 15
    pdf_text_errors = sum(1 for error in errors if error.get("stage") == "process_pdf_text")
    if pdf_text_errors:
        warnings.append(f"{pdf_text_errors} PDF text extraction error(s).")
        score -= min(20, pdf_text_errors * 2)
    filtered_short = sum(1 for event in filtered if event.get("reason") == "document_too_short")
    if filtered_short > max(20, len(documents) * 2):
        warnings.append(f"Many short documents were filtered ({filtered_short}).")
        score -= 5
    candidate_count = sum(1 for chunk in chunks if chunk.metadata.get("vector_candidate", True) is not False)
    candidate_ratio = ratio(candidate_count, len(chunks))
    if chunks and candidate_ratio < 0.25:
        warnings.append(f"vector candidate ratio is low ({candidate_ratio:.0%}).")
        score -= 10

    score = max(0, score)
    return SiteQuality(
        site=site,
        status=status_from_score(score),
        score=score,
        document_count=len(documents),
        chunk_count=len(chunks),
        error_count=len(errors),
        filtered_count=len(filtered),
        warnings=warnings,
        counters={
            "document_type": dict(counter_from_metadata(documents, "document_type")),
            "source_type": dict(counter_from_metadata(chunks, "source_type")),
            "content_type": dict(counter_from_metadata(chunks, "content_type")),
            "vector_candidate": dict(counter_from_metadata(chunks, "vector_candidate")),
            "dept": dict(counter_from_metadata(chunks, "dept")),
            "filtered_reason": dict(Counter(event.get("reason") or "unknown" for event in filtered)),
            "error_stage": dict(Counter(error.get("stage") or "unknown" for error in errors)),
        },
    )


def status_from_score(score: int) -> str:
    if score < 50:
        return "fail"
    if score < 85:
        return "warn"
    return "pass"


def ratio(part: int, total: int) -> float:
    return part / total if total else 0.0


def counter_from_metadata(rows: Iterable[Document | Chunk], key: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = row.metadata[key] if key in row.metadata else "MISSING"
        counter[str(value)] += 1
    return counter


def write_quality_gate_report(
    processed_root: str | Path,
    report: QualityGateReport,
) -> None:
    processed_root = Path(processed_root)
    processed_root.mkdir(parents=True, exist_ok=True)
    (processed_root / "quality_gate.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (processed_root / "quality_gate.md").write_text(quality_gate_markdown(report), encoding="utf-8")


def quality_gate_markdown(report: QualityGateReport) -> str:
    lines = [
        "# Quality Gate",
        "",
        f"- status: `{report.status}`",
        f"- score: `{report.score}`",
        f"- documents: `{report.summary['documents']}`",
        f"- chunks: `{report.summary['chunks']}`",
        f"- vector_candidate_chunks: `{report.summary.get('vector_candidate_chunks', report.summary['chunks'])}`",
        f"- errors: `{report.summary['errors']}`",
        f"- filtered: `{report.summary['filtered']}`",
        "",
        "## Sites",
        "",
        "| site | status | score | documents | chunks | errors | warnings |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for site in report.sites:
        warning_text = "<br>".join(site.warnings) if site.warnings else ""
        lines.append(
            f"| `{site.site}` | `{site.status}` | {site.score} | {site.document_count} | "
            f"{site.chunk_count} | {site.error_count} | {warning_text} |"
        )
    return "\n".join(lines) + "\n"


def load_quality_gate_inputs(output_root: str | Path) -> tuple[list[Document], list[Chunk], list[dict], list[dict]]:
    processed_root = Path(output_root) / "processed"
    documents = [
        Document(
            doc_id=row["doc_id"],
            site=row["site"],
            source_url=row["source_url"],
            title=row["title"],
            text=row["text"],
            raw_path=row.get("raw_path"),
            metadata=row.get("metadata", {}),
        )
        for row in read_jsonl(processed_root / "documents.jsonl")
    ]
    chunks = [
        Chunk(
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            site=row["site"],
            source_url=row["source_url"],
            text=row["text"],
            chunk_index=row["chunk_index"],
            metadata=row.get("metadata", {}),
        )
        for row in read_jsonl(processed_root / "chunks.jsonl")
    ]
    errors = read_jsonl(processed_root / "errors.jsonl")
    filtered = read_jsonl(processed_root / "filtered.jsonl")
    return documents, chunks, errors, filtered


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
