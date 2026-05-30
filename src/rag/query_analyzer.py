from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


RouteType = Literal["sql", "vector", "hybrid", "clarify"]

IntentType = Literal[
    "admission_info",
    "course_info",
    "person_info",
    "office_contact_info",
    "event_info",
    "asset_or_link_info",
    "department_overview",
    "general_info",
]

ContentType = Literal[
    "admission",
    "course",
    "person",
    "office_contact",
    "event",
    "link",
    "mixed_media",
]

ProgramType = Literal[
    "master",
    "doctor",
    "integrated",
]


@dataclass(frozen=True)
class DepartmentInfo:
    name: str
    code: str
    keywords: list[str]


@dataclass(frozen=True)
class IntentRule:
    intent: IntentType
    content_type: ContentType | None
    description: str
    keywords: list[str]
    vector_search_terms: str
    sql_table_hint: str | None
    sql_task_hint: str | None


@dataclass
class QueryAnalysis:
    original_question: str
    normalized_question: str

    route: RouteType
    route_reason: str

    display_question: str
    rewritten_question: str

    department_name: str | None = None
    department_code: str | None = None

    intent: IntentType = "general_info"
    intent_description: str = "일반 정보 질문"
    content_type: ContentType | None = None
    program_type: ProgramType | None = None

    metadata_filter: dict[str, Any] | None = None

    sql_table_hint: str | None = None
    sql_task_hint: str | None = None
    sql_conditions: dict[str, Any] = field(default_factory=dict)

    needs_sql: bool = False
    needs_vector: bool = False

    is_ambiguous: bool = False
    missing_fields: list[str] = field(default_factory=list)
    clarifying_message: str | None = None

    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEPARTMENTS = [
    DepartmentInfo(
        name="AI컴퓨팅학과",
        code="aic",
        keywords=[
            "AI컴퓨팅학과",
            "AI 컴퓨팅학과",
            "AI컴퓨팅",
            "AI 컴퓨팅",
            "AIC",
            "aic",
        ],
    ),
    DepartmentInfo(
        name="AI시스템학과",
        code="ai_systems",
        keywords=[
            "AI시스템학과",
            "AI 시스템학과",
            "AI시스템",
            "AI 시스템",
            "AI Systems",
            "AI systems",
            "ai systems",
            "ai_systems",
        ],
    ),
    DepartmentInfo(
        name="AX학과",
        code="ax",
        keywords=[
            "AX학과",
            "AX 학과",
            "AX",
            "ax",
        ],
    ),
    DepartmentInfo(
        name="AI미래학과",
        code="fx",
        keywords=[
            "AI미래학과",
            "AI 미래학과",
            "AI미래",
            "AI 미래",
            "FX",
            "fx",
        ],
    ),
]


INTENT_RULES = [
    IntentRule(
        intent="course_info",
        content_type="course",
        description="교과목/교육과정 질문",
        keywords=[
            "교과목",
            "과목",
            "강의",
            "수업",
            "커리큘럼",
            "교육과정",
            "전공필수",
            "전공선택",
            "course",
            "courses",
            "curriculum",
            "class",
        ],
        vector_search_terms="교과목 교육과정 커리큘럼 과목 코드 전공필수 전공선택",
        sql_table_hint="courses",
        sql_task_hint="course_lookup",
    ),
    IntentRule(
        intent="office_contact_info",
        content_type="office_contact",
        description="학과 사무실/전화번호/위치 질문",
        keywords=[
            "학과사무실",
            "학과 사무실",
            "사무실",
            "행정실",
            "전화번호",
            "전화",
            "위치",
            "건물",
            "office",
            "contact",
            "phone",
            "location",
        ],
        vector_search_terms="학과사무실 전화번호 위치 웹사이트 연락처 행정실",
        sql_table_hint="office_contacts",
        sql_task_hint="office_contact_lookup",
    ),
    IntentRule(
        intent="person_info",
        content_type="person",
        description="교수진/구성원/이메일 질문",
        keywords=[
            "교수",
            "교수진",
            "구성원",
            "연구실",
            "이메일",
            "메일",
            "홈페이지",
            "people",
            "faculty",
            "professor",
            "email",
        ],
        vector_search_terms="교수진 구성원 이름 역할 이메일 홈페이지 연구실",
        sql_table_hint="professors",
        sql_task_hint="person_lookup",
    ),
    IntentRule(
        intent="admission_info",
        content_type="admission",
        description="입학/지원자격/전형 질문",
        keywords=[
            "입학",
            "지원",
            "지원 자격",
            "지원자격",
            "전형",
            "모집",
            "석사",
            "박사",
            "석박사",
            "통합과정",
            "졸업예정자",
            "admission",
            "apply",
            "eligibility",
        ],
        vector_search_terms="대학원 입학 지원 자격 모집 전형 석사 박사 석박사 통합과정",
        sql_table_hint="admissions",
        sql_task_hint="admission_lookup",
    ),
    IntentRule(
        intent="event_info",
        content_type="event",
        description="공지/행사/설명회 질문",
        keywords=[
            "설명회",
            "학과설명회",
            "행사",
            "공지",
            "일정",
            "세미나",
            "안내",
            "event",
            "notice",
            "seminar",
        ],
        vector_search_terms="공지 행사 설명회 일정 장소 자료 세미나 안내",
        sql_table_hint="events",
        sql_task_hint="event_lookup",
    ),
    IntentRule(
        intent="asset_or_link_info",
        content_type="link",
        description="링크/자료/다운로드 질문",
        keywords=[
            "링크",
            "URL",
            "url",
            "사이트",
            "바로가기",
            "자료",
            "다운로드",
            "pdf",
            "PDF",
            "brochure",
            "download",
        ],
        vector_search_terms="홈페이지 링크 URL 자료 다운로드 PDF 브로슈어",
        sql_table_hint="assets",
        sql_task_hint="asset_lookup",
    ),
    IntentRule(
        intent="department_overview",
        content_type=None,
        description="학과 소개/개요 질문",
        keywords=[
            "학과 소개",
            "소개",
            "어떤 학과",
            "무슨 학과",
            "특징",
            "비전",
            "목표",
            "overview",
            "about",
            "description",
        ],
        vector_search_terms="학과 소개 개요 특징 비전 목표 교육 연구",
        sql_table_hint="departments",
        sql_task_hint="department_overview",
    ),
]


SQL_STRONG_KEYWORDS = [
    "목록",
    "전체",
    "전부",
    "표",
    "표로",
    "리스트",
    "몇 개",
    "개수",
    "이메일",
    "전화번호",
    "연락처",
    "코드",
    "과목코드",
    "전공필수만",
    "전공선택만",
    "있는 사람",
    "없는 사람",
    "조회",
    "정렬",
]

VECTOR_STRONG_KEYWORDS = [
    "설명",
    "요약",
    "근거",
    "내용",
    "자세히",
    "무슨 뜻",
    "어떤",
    "왜",
    "차이",
    "주의사항",
    "조건",
    "자격",
    "안내",
]

HYBRID_STRONG_PATTERNS = [
    ["목록", "설명"],
    ["목록", "근거"],
    ["표", "설명"],
    ["표", "근거"],
    ["교과목", "설명"],
    ["과목", "설명"],
    ["교과목", "추천"],
    ["과목", "추천"],
    ["교수", "연구"],
    ["이메일", "연구"],
    ["입학", "표"],
    ["지원 자격", "근거"],
]


class QuestionAnalyzer:
    def __init__(
        self,
        departments: list[DepartmentInfo] | None = None,
        intent_rules: list[IntentRule] | None = None,
    ) -> None:
        self.departments = departments or DEPARTMENTS
        self.intent_rules = intent_rules or INTENT_RULES

    def analyze(
        self,
        question: str,
        previous_department_code: str | None = None,
    ) -> QueryAnalysis:
        original_question = question
        normalized_question = self._normalize_question(question)

        department = self._find_department(
            normalized_question=normalized_question,
            previous_department_code=previous_department_code,
        )

        intent_rule, matched_keywords = self._find_intent_rule(
            normalized_question=normalized_question,
        )

        department_name = department.name if department else None
        department_code = department.code if department else None

        intent = intent_rule.intent if intent_rule else "general_info"
        intent_description = intent_rule.description if intent_rule else "일반 정보 질문"
        content_type = intent_rule.content_type if intent_rule else None
        program_type = self._detect_program_type(normalized_question)

        route, route_reason = self._decide_route(
            normalized_question=normalized_question,
            intent_rule=intent_rule,
        )

        metadata_filter = self._build_metadata_filter(
            department_code=department_code,
            content_type=content_type,
        )

        sql_conditions = self._build_sql_conditions(
            department_code=department_code,
            content_type=content_type,
        )

        missing_fields = self._find_missing_fields(
            department_code=department_code,
            content_type=content_type,
            intent=intent,
        )

        is_ambiguous = len(missing_fields) > 0
        clarifying_message = None

        if is_ambiguous:
            route = "clarify"
            route_reason = "질문 처리에 필요한 정보가 부족합니다."
            clarifying_message = self._build_clarifying_message(missing_fields)

        rewritten_question = self._build_rewritten_question(
            normalized_question=normalized_question,
            department_name=department_name,
            intent_rule=intent_rule,
            program_type=program_type,
        )

        display_question = self._build_display_question(
            normalized_question=normalized_question,
            department_name=department_name,
            intent_description=intent_description,
            route=route,
        )

        return QueryAnalysis(
            original_question=original_question,
            normalized_question=normalized_question,
            route=route,
            route_reason=route_reason,
            display_question=display_question,
            rewritten_question=rewritten_question,
            department_name=department_name,
            department_code=department_code,
            intent=intent,
            intent_description=intent_description,
            content_type=content_type,
            program_type=program_type,
            metadata_filter=metadata_filter,
            sql_table_hint=intent_rule.sql_table_hint if intent_rule else None,
            sql_task_hint=intent_rule.sql_task_hint if intent_rule else None,
            sql_conditions=sql_conditions,
            needs_sql=route in {"sql", "hybrid"},
            needs_vector=route in {"vector", "hybrid"},
            is_ambiguous=is_ambiguous,
            missing_fields=missing_fields,
            clarifying_message=clarifying_message,
            matched_keywords=matched_keywords,
        )

    def _normalize_question(self, question: str) -> str:
        text = question.strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _find_department(
        self,
        normalized_question: str,
        previous_department_code: str | None,
    ) -> DepartmentInfo | None:
        lowered_question = normalized_question.lower()

        for department in self.departments:
            for keyword in department.keywords:
                if keyword.lower() in lowered_question:
                    return department

        if previous_department_code:
            return self._get_department_by_code(previous_department_code)

        return None

    def _get_department_by_code(
        self,
        department_code: str,
    ) -> DepartmentInfo | None:
        for department in self.departments:
            if department.code == department_code:
                return department

        return None

    def _find_intent_rule(
        self,
        normalized_question: str,
    ) -> tuple[IntentRule | None, list[str]]:
        lowered_question = normalized_question.lower()

        for rule in self.intent_rules:
            matched_keywords = [
                keyword
                for keyword in rule.keywords
                if keyword.lower() in lowered_question
            ]

            if matched_keywords:
                return rule, matched_keywords

        return None, []

    def _detect_program_type(
        self,
        normalized_question: str,
    ) -> ProgramType | None:
        text = normalized_question.lower().replace(" ", "")

        if "석박사" in text or "통합과정" in text or "석사박사통합" in text:
            return "integrated"

        if "박사" in text or "doctoral" in text or "phd" in text:
            return "doctor"

        if "석사" in text or "master" in text:
            return "master"

        return None

    def _decide_route(
        self,
        normalized_question: str,
        intent_rule: IntentRule | None,
    ) -> tuple[RouteType, str]:
        if intent_rule is None:
            return "clarify", "질문 의도를 분류하지 못했습니다."

        lowered_question = normalized_question.lower()

        if self._has_hybrid_pattern(lowered_question):
            return "hybrid", "정형 데이터와 문서 설명이 함께 필요한 질문입니다."

        has_sql_signal = self._contains_any(lowered_question, SQL_STRONG_KEYWORDS)
        has_vector_signal = self._contains_any(lowered_question, VECTOR_STRONG_KEYWORDS)

        if has_sql_signal and has_vector_signal:
            return "hybrid", "SQL 조회와 문서 기반 설명이 모두 필요한 질문입니다."

        if has_sql_signal:
            return "sql", "정확한 목록, 표, 연락처, 조건 조회가 필요한 질문입니다."

        if has_vector_signal:
            return "vector", "문서 기반 설명이나 근거가 필요한 질문입니다."

        if intent_rule.intent in {
            "course_info",
            "person_info",
            "office_contact_info",
            "asset_or_link_info",
        }:
            return "sql", "정확한 정형 데이터 조회가 적합한 질문입니다."

        if intent_rule.intent in {
            "admission_info",
            "event_info",
            "department_overview",
        }:
            return "vector", "문서 내용과 설명 근거가 중요한 질문입니다."

        return "vector", "일반 문서 검색이 적합한 질문입니다."

    def _has_hybrid_pattern(self, lowered_question: str) -> bool:
        return any(
            all(keyword.lower() in lowered_question for keyword in pattern)
            for pattern in HYBRID_STRONG_PATTERNS
        )

    def _contains_any(self, text: str, keywords: list[str]) -> bool:
        return any(keyword.lower() in text for keyword in keywords)

    def _build_rewritten_question(
        self,
        normalized_question: str,
        department_name: str | None,
        intent_rule: IntentRule | None,
        program_type: ProgramType | None = None,
    ) -> str:
        parts = [normalized_question]
    
        if department_name and department_name not in normalized_question:
            parts.append(department_name)
    
        if intent_rule:
            if intent_rule.intent == "admission_info" and program_type:
                parts.append("대학원 입학 지원 자격 모집 전형")
    
                if program_type == "master":
                    parts.append("석사과정 석사 지원 자격 학사학위자")
                elif program_type == "doctor":
                    parts.append("박사과정 박사 지원 자격 석사학위자")
                elif program_type == "integrated":
                    parts.append("석박사 통합과정 통합과정 지원 자격")
            else:
                parts.append(intent_rule.vector_search_terms)
    
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    def _build_display_question(
        self,
        normalized_question: str,
        department_name: str | None,
        intent_description: str,
        route: RouteType,
    ) -> str:
        if department_name:
            return f"[{route.upper()}] {department_name}에 대한 {intent_description}: {normalized_question}"

        return f"[{route.upper()}] {intent_description}: {normalized_question}"

    def _build_metadata_filter(
        self,
        department_code: str | None,
        content_type: ContentType | None,
    ) -> dict[str, Any] | None:
        conditions = []

        if department_code:
            conditions.append({"dept": {"$eq": department_code}})

        if content_type:
            conditions.append({"content_type": {"$eq": content_type}})

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        return {"$and": conditions}

    def _build_sql_conditions(
        self,
        department_code: str | None,
        content_type: ContentType | None,
    ) -> dict[str, Any]:
        conditions = {}

        if department_code:
            conditions["dept"] = department_code

        if content_type:
            conditions["content_type"] = content_type

        return conditions

    def _find_missing_fields(
        self,
        department_code: str | None,
        content_type: ContentType | None,
        intent: IntentType,
    ) -> list[str]:
        missing_fields = []

        if intent == "general_info" and content_type is None:
            missing_fields.append("intent_or_content_type")

        if content_type in {"course", "person", "admission", "event"}:
            if department_code is None:
                missing_fields.append("department")

        if intent == "department_overview" and department_code is None:
            missing_fields.append("department")

        return missing_fields

    def _build_clarifying_message(self, missing_fields: list[str]) -> str:
        if "department" in missing_fields:
            examples = ", ".join(department.name for department in self.departments)
            return f"어느 학과에 대한 질문인지 알려주세요. 예: {examples}"

        if "intent_or_content_type" in missing_fields:
            return (
                "어떤 정보를 알고 싶은지 조금 더 구체적으로 질문해주세요. "
                "예: 입학 정보, 교과목, 교수진, 학과 사무실, 설명회 정보"
            )

        return "질문을 조금 더 구체적으로 입력해주세요."


def run_examples() -> None:
    analyzer = QuestionAnalyzer()

    questions = [
        "AI컴퓨팅학과 석사 지원 자격은?",
        "AI컴퓨팅학과 박사 지원 자격은?",
        "AI컴퓨팅학과 석박사 통합과정 지원 자격은?",
        "AI컴퓨팅학과 학과설명회 정보 알려줘",
        "AI시스템학과 교과목 알려줘",
        "AI시스템학과 교과목 목록과 각 과목 설명도 알려줘",
        "AX학과 교수진 이메일 목록 보여줘",
        "AX학과 교수 연구분야도 설명해줘",
        "KAIST 학과 사무실 전화번호 알려줘",
        "교수진도 알려줘",
    ]

    for question in questions:
        analysis = analyzer.analyze(question)
        print("=" * 100)
        print(f"질문: {question}")
        print(analysis.to_dict())


if __name__ == "__main__":
    run_examples()