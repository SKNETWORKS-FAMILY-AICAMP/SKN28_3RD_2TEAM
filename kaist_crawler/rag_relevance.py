from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import requests

from .models import Document
from .store import stable_id


DEFAULT_LLM_RELEVANCE_MODEL = "gpt-4o-mini"


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


KEEP_CONTENT_TYPES = {
    "admission": 95,
    "requirement": 92,
    "course": 90,
    "scholarship": 90,
    "office_contact": 82,
    "department_profile": 78,
    "person": 85,
}

POSITIVE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("admission", r"입학|입시|모집|지원\s*자격|전형|admission|apply|graduate admission"),
    ("requirement", r"졸업\s*요건|수료\s*요건|이수\s*요건|graduation|requirement|required credits"),
    ("course", r"교육과정|교과목|커리큘럼|전공필수|curriculum|course|credits"),
    ("scholarship", r"장학|장학금|등록금|수업료|tuition|scholarship"),
    ("person", r"교수진|교수|연구실|faculty|professor|research interests"),
    ("office_contact", r"학과사무실|행정실|문의|연락처|전화번호|contact|office"),
    ("department_profile", r"학과\s*소개|대학원\s*소개|비전|교육목표|vision|mission|overview"),
)

DROP_PATTERNS: tuple[tuple[str, str], ...] = (
    ("old_exam", r"oldexam|old[-_ ]?exam|past[-_ ]?exam|midterm|final|qualifying exam|박사자격시험|기출"),
    ("newsletter", r"newsletter|magazine|annual report|소식지|뉴스레터|매거진|연례보고"),
    ("job", r"채용|임용|직원\s*채용|recruitment|job opening|position announcement"),
    ("seminar", r"세미나|콜로퀴움|seminar|colloquium|workshop"),
    ("event", r"행사|시상|수상|강연|event|ceremony|award"),
    ("form", r"양식|신청서|서식|form|application form"),
)


def classify_documents(
    documents: list[Document],
    *,
    use_llm: bool = False,
    llm_model: str | None = None,
    max_llm: int | None = None,
    cache_path: str | Path | None = None,
) -> list[RelevanceDecision]:
    cache = RelevanceCache(cache_path) if cache_path else None
    llm_client: LlmRelevanceClient | None = None
    llm_error = ""
    if use_llm:
        try:
            llm_client = OpenAiRelevanceClient(model=llm_model)
        except Exception as exc:
            llm_error = f"{type(exc).__name__}: {exc}"
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
        elif use_llm and llm_client is not None and rule_decision.needs_llm and max_llm is not None and llm_used >= max_llm:
            decision = RelevanceDecision(
                vector_candidate=decision.vector_candidate,
                rag_priority=decision.rag_priority,
                content_type=decision.content_type,
                reason=f"{decision.reason}; LLM limit reached ({max_llm})",
                source="rule_fallback",
                label=decision.label,
                needs_llm=True,
            )
        if use_llm and llm_client is None and decision.needs_llm:
            decision = RelevanceDecision(
                vector_candidate=decision.vector_candidate,
                rag_priority=decision.rag_priority,
                content_type=decision.content_type,
                reason=f"{decision.reason}; LLM client unavailable: {llm_error}",
                source="rule_fallback",
                label=decision.label,
                needs_llm=True,
            )
        document.metadata.update(decision.metadata())
        decisions.append(decision)
    if cache:
        try:
            cache.write()
        except Exception:
            pass
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
            return RelevanceDecision(
                vector_candidate=rule_decision.vector_candidate,
                rag_priority=rule_decision.rag_priority,
                content_type=rule_decision.content_type,
                reason=f"{rule_decision.reason}; LLM disabled, used rule fallback",
                source="rule_fallback",
                label=rule_decision.label,
                needs_llm=True,
            )
        return rule_decision

    cache_key = relevance_cache_key(document)
    cached = cache.get(cache_key) if cache else None
    if cached:
        return cached
    try:
        llm_decision = llm_client.classify(document)
    except Exception as exc:
        return RelevanceDecision(
            vector_candidate=rule_decision.vector_candidate,
            rag_priority=rule_decision.rag_priority,
            content_type=rule_decision.content_type,
            reason=f"{rule_decision.reason}; LLM failed: {type(exc).__name__}: {exc}",
            source="rule_fallback",
            label=rule_decision.label,
            needs_llm=True,
        )
    if cache:
        cache.set(cache_key, llm_decision)
    return llm_decision


def rule_based_relevance(document: Document) -> RelevanceDecision:
    metadata = document.metadata
    content_type = str(metadata.get("content_type") or "general")
    source_type = str(metadata.get("source_type") or "")
    document_type = str(metadata.get("document_type") or "")
    target = relevance_text(document)

    positive_label, positive_hits = best_match(target, POSITIVE_PATTERNS)
    drop_label, drop_hits = best_match(target, DROP_PATTERNS)

    if drop_label and not strong_positive_override(positive_label, positive_hits, content_type):
        return RelevanceDecision(
            vector_candidate=False,
            rag_priority=10,
            content_type=drop_label,
            reason=f"Excluded by low-value pattern: {drop_label}",
            source="rule",
            label=drop_label,
        )

    if content_type in KEEP_CONTENT_TYPES:
        return RelevanceDecision(
            vector_candidate=True,
            rag_priority=KEEP_CONTENT_TYPES[content_type],
            content_type=content_type,
            reason=f"Kept by counseling content type: {content_type}",
            source="rule",
            label=f"keep_{content_type}",
        )

    if source_type in {"faculty"} or document_type == "faculty":
        return RelevanceDecision(
            vector_candidate=True,
            rag_priority=85,
            content_type="person",
            reason="Kept faculty/person document for counseling.",
            source="rule",
            label="keep_faculty",
        )

    if positive_label and positive_hits >= 2:
        return RelevanceDecision(
            vector_candidate=True,
            rag_priority=70 if source_type == "pdf" else 75,
            content_type=positive_label,
            reason=f"Kept by counseling keywords: {positive_label}",
            source="rule",
            label=f"keep_keyword_{positive_label}",
        )

    if document_type == "spa_bundle_text":
        return RelevanceDecision(
            vector_candidate=bool(positive_label),
            rag_priority=60 if positive_label else 35,
            content_type=positive_label or content_type,
            reason="SPA bundle fallback requires relevance review.",
            source="rule",
            label="ambiguous_spa_bundle",
            needs_llm=True,
        )

    if source_type == "pdf" or document_type == "pdf":
        return RelevanceDecision(
            vector_candidate=False,
            rag_priority=25,
            content_type=content_type,
            reason="General PDF requires relevance review before vector storage.",
            source="rule",
            label="ambiguous_pdf",
            needs_llm=True,
        )

    if content_type in {"event", "news", "general"}:
        return RelevanceDecision(
            vector_candidate=False,
            rag_priority=30,
            content_type=content_type,
            reason=f"{content_type} document requires relevance review.",
            source="rule",
            label=f"ambiguous_{content_type}",
            needs_llm=True,
        )

    return RelevanceDecision(
        vector_candidate=False,
        rag_priority=20,
        content_type=content_type,
        reason="No counseling relevance signal was found.",
        source="rule",
        label="drop_no_signal",
    )


def relevance_text(document: Document) -> str:
    metadata = document.metadata
    parts = [
        document.source_url,
        document.title,
        str(metadata.get("section") or ""),
        str(metadata.get("file_name") or ""),
        str(metadata.get("category") or ""),
        document.text[:4000],
    ]
    return " ".join(part for part in parts if part).lower()


def best_match(value: str, patterns: tuple[tuple[str, str], ...]) -> tuple[str, int]:
    best_label = ""
    best_hits = 0
    for label, pattern in patterns:
        hits = len(re.findall(pattern, value, flags=re.IGNORECASE))
        if hits > best_hits:
            best_label = label
            best_hits = hits
    return best_label, best_hits


def strong_positive_override(label: str, hits: int, content_type: str) -> bool:
    if content_type in {"admission", "requirement", "course", "scholarship"}:
        return True
    return label in {"admission", "requirement", "course", "scholarship"} and hits >= 2


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
        data = json.loads(content)
        return normalize_llm_decision(data)


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
