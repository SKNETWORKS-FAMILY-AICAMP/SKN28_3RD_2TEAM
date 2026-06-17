from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DepartmentInfo:
    code: str
    name: str
    sites: tuple[str, ...]
    keywords: tuple[str, ...]


DEPARTMENTS: tuple[DepartmentInfo, ...] = (
    DepartmentInfo(
        code="aic",
        name="AI컴퓨팅학과",
        sites=("kaist_aic",),
        keywords=("AI컴퓨팅", "AI 컴퓨팅", "AI Computing", "AIC", "컴퓨팅학과"),
    ),
    DepartmentInfo(
        code="ai_systems",
        name="AI시스템학과",
        sites=("kaist_ai_systems",),
        keywords=("AI시스템", "AI 시스템", "AI Systems", "AI System", "시스템학과"),
    ),
    DepartmentInfo(
        code="ax",
        name="AX학과",
        sites=("kaist_ax",),
        keywords=("AX학과", "AX 학과", "AI Transformation", "AX"),
    ),
    DepartmentInfo(
        code="fx",
        name="AI미래학과",
        sites=("kaist_fx",),
        keywords=("AI미래", "AI 미래", "AI and Futures", "Futures Studies", "FX", "미래학과"),
    ),
)

SITE_DEPARTMENT = {
    site: department
    for department in DEPARTMENTS
    for site in department.sites
}

SOURCE_TYPE_BY_DOCUMENT_TYPE = {
    "html": "html",
    "rendered_html": "html",
    "html_shell": "html",
    "pdf": "pdf",
    "news": "news",
    "faculty": "faculty",
    "google_sheet": "sheet",
    "spa_bundle_text": "spa_bundle_text",
}

CONTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "scholarship",
        (
            "장학",
            "장학금",
            "scholarship",
            "등록금",
            "수업료",
            "납부",
            "tuition",
        ),
    ),
    (
        "office_contact",
        (
            "학과사무실",
            "사무실",
            "행정실",
            "문의처",
            "연락처",
            "전화번호",
            "phone",
            "contact",
            "office",
        ),
    ),
    (
        "person",
        (
            "교수",
            "교수진",
            "구성원",
            "연구실",
            "faculty",
            "professor",
            "research interests",
            "email",
            "name_ko",
            "name_en",
        ),
    ),
    (
        "requirement",
        (
            "졸업요건",
            "졸업 요건",
            "수료요건",
            "수료 요건",
            "이수요건",
            "이수 요건",
            "graduation requirements",
            "degree requirements",
            "required credits",
        ),
    ),
    (
        "course",
        (
            "교과목",
            "교육과정",
            "커리큘럼",
            "전공필수",
            "전공선택",
            "course",
            "courses",
            "curriculum",
            "credits",
        ),
    ),
    (
        "admission",
        (
            "입학",
            "입시",
            "입시설명회",
            "지원 자격",
            "지원자격",
            "모집",
            "전형",
            "석사",
            "박사",
            "석박사",
            "admission",
            "apply",
            "graduate admission",
            "info session",
        ),
    ),
    (
        "event",
        (
            "공지",
            "행사",
            "세미나",
            "설명회",
            "일정",
            "news",
            "notice",
            "event",
            "seminar",
        ),
    ),
    (
        "department_profile",
        (
            "학과 소개",
            "소개",
            "비전",
            "교육목표",
            "인재상",
            "연구 분야",
            "vision",
            "mission",
            "overview",
            "about",
        ),
    ),
)

ROUTE_CONTENT_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("admission", ("admission", "admissions", "grad", "입학", "입시")),
    ("person", ("people", "faculty", "professor", "교수")),
    ("course", ("course", "curriculum", "education-courses", "course-information", "교과")),
    ("requirement", ("requirements", "education-reqs", "graduation", "졸업", "이수")),
    ("event", ("news", "notice", "event", "seminar", "공지")),
    ("department_profile", ("intro", "about", "dept-intro", "welcome", "vision", "학과소개")),
)


def normalize_rag_metadata(
    *,
    site: str,
    source_url: str,
    title: str,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(metadata)
    document_type = str(normalized.get("document_type") or "")

    if site == "kaist_ai_college" and not normalized.get("dept"):
        normalized.setdefault("dept", "ai_college")
        normalized.setdefault("dept_name", "KAIST AI College")
    elif site == "kaist_main_kr" and not normalized.get("dept"):
        normalized.setdefault("dept", "kaist")
        normalized.setdefault("dept_name", "KAIST")
    else:
        department = detect_department(
            site=site,
            source_url=source_url,
            title=title,
            text=text,
            metadata=normalized,
        )
        if department:
            normalized.setdefault("dept", department.code)
            normalized.setdefault("dept_name", department.name)

    normalized.setdefault("source_type", infer_source_type(document_type))
    normalized.setdefault(
        "content_type",
        infer_content_type(
            site=site,
            source_url=source_url,
            title=title,
            text=text,
            metadata=normalized,
        ),
    )

    section = normalized.get("section")
    if not section:
        inferred_section = infer_section_title(text, fallback=title)
        if inferred_section:
            normalized["section"] = inferred_section

    return normalized


def detect_department(
    *,
    site: str,
    source_url: str = "",
    title: str = "",
    text: str = "",
    metadata: dict[str, Any] | None = None,
) -> DepartmentInfo | None:
    metadata = metadata or {}
    explicit_code = str(metadata.get("dept") or "")
    if explicit_code:
        for department in DEPARTMENTS:
            if department.code == explicit_code:
                return department

    if site in SITE_DEPARTMENT:
        return SITE_DEPARTMENT[site]

    haystack = " ".join([source_url, title, text[:3000]]).lower()
    for department in DEPARTMENTS:
        if any(keyword.lower() in haystack for keyword in department.keywords):
            return department
    return None


def infer_source_type(document_type: str) -> str:
    return SOURCE_TYPE_BY_DOCUMENT_TYPE.get(document_type, document_type or "unknown")


def infer_content_type(
    *,
    site: str,
    source_url: str,
    title: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    metadata = metadata or {}
    document_type = str(metadata.get("document_type") or "").lower()
    if document_type == "faculty":
        return "person"
    if document_type == "news":
        return "admission" if has_keywords(" ".join([title, text]), CONTENT_KEYWORDS[5][1]) else "event"

    route = str(metadata.get("route") or source_url)
    if document_type != "pdf":
        route_content_type = content_type_from_route(route)
        if route_content_type:
            return route_content_type

    haystack = " ".join(
        [
            str(metadata.get("section") or ""),
            str(metadata.get("category") or ""),
            text[:5000],
        ]
    )
    scored_content_type = score_content_types(haystack)
    if scored_content_type:
        return scored_content_type

    route_content_type = content_type_from_route(route)
    if route_content_type:
        return route_content_type

    fallback_haystack = " ".join([site, source_url, title, str(metadata.get("section") or ""), text[:1000]])
    for content_type, keywords in CONTENT_KEYWORDS:
        if has_keywords(fallback_haystack, keywords):
            return content_type
    return "general"


def content_type_from_route(route: str) -> str | None:
    value = route.lower()
    for content_type, hints in ROUTE_CONTENT_HINTS:
        if any(hint.lower() in value for hint in hints):
            return content_type
    return None


def infer_section_title(text: str, *, fallback: str = "") -> str:
    for line in text.splitlines()[:8]:
        candidate = re.sub(r"\s+", " ", line).strip(" -:\t")
        if not candidate:
            continue
        if len(candidate) > 90:
            continue
        if re.fullmatch(r"[\d\s./:-]+", candidate):
            continue
        return candidate
    return fallback.strip()


def has_keywords(value: str, keywords: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def score_content_types(value: str) -> str | None:
    lowered = value.lower()
    scores: list[tuple[int, int, str]] = []
    for order, (content_type, keywords) in enumerate(CONTENT_KEYWORDS):
        score = 0
        for keyword in keywords:
            score += lowered.count(keyword.lower())
        if score > 0:
            scores.append((score, -order, content_type))
    if not scores:
        return None
    scores.sort(reverse=True)
    return scores[0][2]


def content_types_for_query(question: str) -> list[str]:
    lowered = question.lower()
    matched: list[str] = []
    for content_type, keywords in CONTENT_KEYWORDS:
        if any(keyword.lower() in lowered for keyword in keywords):
            matched.append(content_type)

    if "입시설명회" in question and "event" not in matched:
        matched.append("event")
    if "교수진" in question and "person" not in matched:
        matched.append("person")
    if "교육과정" in question and "course" not in matched:
        matched.append("course")

    return dedupe(matched)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        results.append(value)
    return results
