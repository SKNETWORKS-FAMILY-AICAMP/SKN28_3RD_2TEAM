from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests

from .models import Document
from .relevance_rules import rule_based_relevance
from .relevance_types import LlmRelevanceClient, RelevanceDecision
from .store import stable_id


DEFAULT_LLM_RELEVANCE_MODEL = "gpt-4o-mini"


def classify_documents(
    documents: list[Document],
    *,
    use_llm: bool = False,
    llm_model: str | None = None,
    max_llm: int | None = None,
    cache_path: str | Path | None = None,
) -> list[RelevanceDecision]:
    cache = RelevanceCache(cache_path) if cache_path else None
    llm_client, llm_error = build_llm_client(use_llm=use_llm, llm_model=llm_model)
    decisions: list[RelevanceDecision] = []
    llm_used = 0

    for document in documents:
        rule_decision = rule_based_relevance(document)
        can_use_llm = (
            llm_client is not None
            and rule_decision.needs_llm
            and (max_llm is None or llm_used < max_llm)
        )
        decision = classify_document(
            document,
            llm_client=llm_client if can_use_llm else None,
            cache=cache,
            rule_decision=rule_decision,
        )
        if decision.source == "llm":
            llm_used += 1
        elif should_mark_llm_limit_reached(
            use_llm=use_llm,
            llm_client=llm_client,
            rule_decision=rule_decision,
            max_llm=max_llm,
            llm_used=llm_used,
        ):
            decision = rule_fallback_decision(
                decision,
                reason_suffix=f"LLM limit reached ({max_llm})",
            )
        if use_llm and llm_client is None and decision.needs_llm:
            decision = rule_fallback_decision(
                decision,
                reason_suffix=f"LLM client unavailable: {llm_error}",
            )
        document.metadata.update(decision.metadata())
        decisions.append(decision)

    write_cache_safely(cache)
    return decisions


def classify_document(
    document: Document,
    *,
    llm_client: LlmRelevanceClient | None = None,
    cache: "RelevanceCache | None" = None,
    rule_decision: RelevanceDecision | None = None,
) -> RelevanceDecision:
    rule_decision = rule_decision or rule_based_relevance(document)
    if not rule_decision.needs_llm or llm_client is None:
        if rule_decision.needs_llm:
            return rule_fallback_decision(rule_decision, reason_suffix="LLM disabled, used rule fallback")
        return rule_decision

    cache_key = relevance_cache_key(document)
    cached = cache.get(cache_key) if cache else None
    if cached:
        return cached
    try:
        llm_decision = llm_client.classify(document)
    except Exception as exc:
        return rule_fallback_decision(
            rule_decision,
            reason_suffix=f"LLM failed: {type(exc).__name__}: {exc}",
        )
    if cache:
        cache.set(cache_key, llm_decision)
    return llm_decision


def build_llm_client(
    *,
    use_llm: bool,
    llm_model: str | None,
) -> tuple[LlmRelevanceClient | None, str]:
    if not use_llm:
        return None, ""
    try:
        return OpenAiRelevanceClient(model=llm_model), ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def should_mark_llm_limit_reached(
    *,
    use_llm: bool,
    llm_client: LlmRelevanceClient | None,
    rule_decision: RelevanceDecision,
    max_llm: int | None,
    llm_used: int,
) -> bool:
    return (
        use_llm
        and llm_client is not None
        and rule_decision.needs_llm
        and max_llm is not None
        and llm_used >= max_llm
    )


def rule_fallback_decision(decision: RelevanceDecision, *, reason_suffix: str) -> RelevanceDecision:
    return RelevanceDecision(
        vector_candidate=decision.vector_candidate,
        rag_priority=decision.rag_priority,
        content_type=decision.content_type,
        reason=f"{decision.reason}; {reason_suffix}",
        source="rule_fallback",
        label=decision.label,
        needs_llm=True,
    )


def write_cache_safely(cache: "RelevanceCache | None") -> None:
    if cache is None:
        return
    try:
        cache.write()
    except Exception:
        return


class OpenAiRelevanceClient:
    def __init__(self, *, model: str | None = None) -> None:
        load_relevance_env(Path(".env"))
        self.model = model or os.getenv("OPENAI_RELEVANCE_MODEL") or DEFAULT_LLM_RELEVANCE_MODEL
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM relevance classification")

    def classify(self, document: Document) -> RelevanceDecision:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": RELEVANCE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(document_payload(document), ensure_ascii=False)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = post_with_retries(f"{self.base_url}/chat/completions", headers=headers, payload=payload)
        content = response["choices"][0]["message"]["content"]
        return normalize_llm_decision(json.loads(content))


RELEVANCE_SYSTEM_PROMPT = """You are a relevance classifier for a graduate school counseling RAG chatbot.
Keep documents that help answer official counseling questions about admissions, eligibility, schedules, tuition, scholarships, curriculum, graduation requirements, faculty, labs, contacts, and academic policy.
Drop old exams, seminar notices, event reports, job postings, press/news, newsletters, magazines, forms, calendars, and pages with mostly navigation or boilerplate.
Return JSON only with: vector_candidate boolean, rag_priority integer 0-100, content_type string, reason string."""


def document_payload(document: Document) -> dict[str, Any]:
    metadata = document.metadata
    return {
        "site": document.site,
        "source_url": document.source_url,
        "title": document.title,
        "document_type": metadata.get("document_type", ""),
        "source_type": metadata.get("source_type", ""),
        "current_content_type": metadata.get("content_type", ""),
        "dept": metadata.get("dept", ""),
        "dept_name": metadata.get("dept_name", ""),
        "text_preview": document.text[:3000],
    }


def normalize_llm_decision(data: dict[str, Any]) -> RelevanceDecision:
    return RelevanceDecision(
        vector_candidate=bool(data.get("vector_candidate")),
        rag_priority=max(0, min(100, int(data.get("rag_priority", 0)))),
        content_type=str(data.get("content_type") or "general"),
        reason=str(data.get("reason") or "LLM relevance decision"),
        source="llm",
        label="llm_decision",
        needs_llm=True,
    )


def post_with_retries(url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
                continue
    raise RuntimeError(f"LLM relevance request failed: {last_error}") from last_error


def load_relevance_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in {"OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_RELEVANCE_MODEL"}:
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def relevance_cache_key(document: Document) -> str:
    return stable_id(document.site, document.source_url, document.title, document.text[:5000])


class RelevanceCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._values: dict[str, RelevanceDecision] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                self._values[row["key"]] = RelevanceDecision(**row["decision"])

    def get(self, key: str) -> RelevanceDecision | None:
        return self._values.get(key)

    def set(self, key: str, decision: RelevanceDecision) -> None:
        self._values[key] = decision

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            for key, decision in sorted(self._values.items()):
                row = {"key": key, "decision": asdict(decision)}
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
