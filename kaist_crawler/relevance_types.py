from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .models import Document


@dataclass(frozen=True)
class RelevanceDecision:
    vector_candidate: bool
    rag_priority: int
    content_type: str
    reason: str
    source: str
    label: str
    needs_llm: bool = False

    def metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["relevance_source"] = payload.pop("source")
        payload["relevance_label"] = payload.pop("label")
        payload["relevance_needs_llm"] = payload.pop("needs_llm")
        payload["relevance_reason"] = payload.pop("reason")
        return payload


class LlmRelevanceClient(Protocol):
    def classify(self, document: Document) -> RelevanceDecision:
        ...
