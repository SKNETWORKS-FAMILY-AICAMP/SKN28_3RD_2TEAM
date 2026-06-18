from __future__ import annotations

import re

from .models import Document
from .relevance_types import RelevanceDecision


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
    ("job", r"채용|직원\s*채용|recruitment|job opening|position announcement"),
    ("seminar", r"세미나|콜로퀴움|seminar|colloquium|workshop"),
    ("event", r"행사|시상|수상|강연|event|ceremony|award"),
    ("form", r"양식|신청서|서식|form|application form"),
)


def rule_based_relevance(document: Document) -> RelevanceDecision:
    metadata = document.metadata
    content_type = str(metadata.get("content_type") or "general")
    source_type = str(metadata.get("source_type") or "")
    document_type = str(metadata.get("document_type") or "")
    target = relevance_text(document)

    positive_label, positive_hits = best_match(target, POSITIVE_PATTERNS)
    drop_label, _drop_hits = best_match(target, DROP_PATTERNS)

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
