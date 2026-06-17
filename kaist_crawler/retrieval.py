from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .rag_metadata import content_types_for_query, detect_department


@dataclass(frozen=True)
class RetrievalAnalysis:
    question: str
    dept: str | None = None
    dept_name: str | None = None
    content_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "dept": self.dept,
            "dept_name": self.dept_name,
            "content_types": self.content_types,
        }


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk_id: str
    document: str
    metadata: dict[str, Any]
    distance: float
    stage: str
    where: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "chunk_id": self.chunk_id,
            "document": self.document,
            "metadata": self.metadata,
            "distance": self.distance,
            "stage": self.stage,
        }
        if self.where:
            payload["where"] = self.where
        return payload


def analyze_retrieval_query(question: str) -> RetrievalAnalysis:
    department = detect_department(site="", title=question, text=question)
    return RetrievalAnalysis(
        question=question,
        dept=department.code if department else None,
        dept_name=department.name if department else None,
        content_types=content_types_for_query(question),
    )


def retrieve_with_metadata_filters(
    *,
    collection: Any,
    query_embedding: list[float],
    question: str,
    top_k: int,
    fetch_k: int | None = None,
) -> tuple[RetrievalAnalysis, list[RetrievalCandidate]]:
    analysis = analyze_retrieval_query(question)
    fetch_k = fetch_k or max(top_k * 4, top_k)
    candidates: list[RetrievalCandidate] = []
    seen_ids: set[str] = set()

    for stage, where in build_filter_plan(analysis):
        batch = query_collection(
            collection=collection,
            query_embedding=query_embedding,
            n_results=fetch_k,
            where=where,
            stage=stage,
        )
        for candidate in batch:
            if candidate.chunk_id in seen_ids:
                continue
            seen_ids.add(candidate.chunk_id)
            candidates.append(candidate)
        if len(candidates) >= top_k:
            break

    return analysis, candidates[:top_k]


def retrieve_without_filters(
    *,
    collection: Any,
    query_embedding: list[float],
    top_k: int,
) -> list[RetrievalCandidate]:
    return query_collection(
        collection=collection,
        query_embedding=query_embedding,
        n_results=top_k,
        where=None,
        stage="no_filter",
    )


def build_filter_plan(analysis: RetrievalAnalysis) -> list[tuple[str, dict[str, Any] | None]]:
    plan: list[tuple[str, dict[str, Any] | None]] = []
    content_types = analysis.content_types

    if analysis.dept and content_types:
        for content_type in content_types:
            plan.append(("strict_filter", and_where({"dept": analysis.dept}, {"content_type": content_type})))

    if analysis.dept:
        plan.append(("department_only", {"dept": analysis.dept}))

    for content_type in content_types:
        plan.append(("content_type_only", {"content_type": content_type}))

    plan.append(("no_filter", None))
    return dedupe_plan(plan)


def and_where(*conditions: dict[str, Any]) -> dict[str, Any]:
    non_empty = [condition for condition in conditions if condition]
    if len(non_empty) == 1:
        return non_empty[0]
    return {"$and": non_empty}


def dedupe_plan(plan: list[tuple[str, dict[str, Any] | None]]) -> list[tuple[str, dict[str, Any] | None]]:
    results: list[tuple[str, dict[str, Any] | None]] = []
    seen: set[str] = set()
    for stage, where in plan:
        key = repr(where)
        if key in seen:
            continue
        seen.add(key)
        results.append((stage, where))
    return results


def query_collection(
    *,
    collection: Any,
    query_embedding: list[float],
    n_results: int,
    where: dict[str, Any] | None,
    stage: str,
) -> list[RetrievalCandidate]:
    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    try:
        results = collection.query(**kwargs)
    except Exception:
        if where is None:
            raise
        return []

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    candidates: list[RetrievalCandidate] = []
    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        candidates.append(
            RetrievalCandidate(
                chunk_id=str(chunk_id),
                document=document or "",
                metadata=dict(metadata or {}),
                distance=float(distance),
                stage=stage,
                where=where,
            )
        )
    return candidates
