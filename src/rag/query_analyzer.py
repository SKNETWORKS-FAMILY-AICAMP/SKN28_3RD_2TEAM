from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


# ============================================================
# 1. 타입 정의
# ============================================================

RouteType = Literal["sql", "vector", "hybrid", "clarify"]

AmbiguityType = Literal[
    "department_scope",
    "missing_department",
    "missing_intent",
    "too_broad",
    "comparison_criterion",
    "personal_recommendation",
    "unclear_reference",
    "unsupported_kaist_department",
    "unsupported_fact",
    "off_topic",
]

IntentType = Literal[
    "admission_info",
    "course_info",
    "person_info",
    "office_contact_info",
    "event_info",
    "asset_or_link_info",
    "department_overview",
    "department_homepage_info",
    "recommendation_info",
    "comparison_info",
    "requirement_info",
    "kaist_profile_info",
    "kaist_statistics_info",
    "kaist_link_info",
    "general_info",
]

ContentType = Literal[
    "admission",
    "course",
    "person",
    "office_contact",
    "event",
    "link",
    "kaist_profile",
    "kaist_statistics",
    "mixed_media",
    "department_homepage",
    "requirement",
    "department_profile",
    "recommendation",
]


# ============================================================
# 2. dataclass
# ============================================================

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


@dataclass(frozen=True)
class IntentExample:
    text: str
    intent: IntentType = "general_info"
    ambiguity_type: AmbiguityType | None = None


@dataclass(frozen=True)
class IntentExampleMatch:
    example: IntentExample
    score: float


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
    department_names: list[str] = field(default_factory=list)
    department_codes: list[str] = field(default_factory=list)
    is_multi_department: bool = False
    unsupported_department_name: str | None = None

    intent: IntentType = "general_info"
    intent_description: str = "일반 정보 질문"
    content_type: ContentType | None = None

    metadata_filter: dict[str, Any] | None = None

    sql_table_hint: str | None = None
    sql_task_hint: str | None = None
    sql_conditions: dict[str, Any] = field(default_factory=dict)

    needs_sql: bool = False
    needs_vector: bool = False

    is_ambiguous: bool = False
    ambiguity_type: AmbiguityType | None = None
    missing_fields: list[str] = field(default_factory=list)
    clarifying_message: str | None = None

    matched_keywords: list[str] = field(default_factory=list)
    semantic_match_intent: str | None = None
    semantic_match_ambiguity_type: str | None = None
    semantic_match_score: float | None = None
    semantic_match_example: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# 3. 학과 / 범위 / 예외 키워드
# ============================================================

DEPARTMENTS = [
    DepartmentInfo(
        name="AI컴퓨팅학과",
        code="aic",
        keywords=[
            "AI컴퓨팅학과",
            "AI 컴퓨팅학과",
            "AI컴퓨팅",
            "AI 컴퓨팅",
            "컴퓨팅학과",
            "컴퓨팅",
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
            "시스템학과",
            "시스템",
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
            "AI Transformation",
            "AI transformation",
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
            "미래학과",
            "미래",
            "FX",
            "fx",
        ],
    ),
]

AI_COLLEGE_SCOPE_KEYWORDS = [
    "AI대학",
    "AI 대학",
    "KAIST AI대학",
    "카이스트 AI대학",
    "AI College",
    "AI college",
    "AI 관련 학과",
    "수집된 AI 관련 학과",
    "전체 학과",
    "모든 학과",
    "각 학과",
    "학과별",
    "학과들",
    "학과들을",
    "네 개 학과",
    "4개 학과",
]

UNSUPPORTED_FACT_KEYWORDS = [
    "경쟁률",
    "등록금",
    "평균 연봉",
    "연봉",
    "취업률",
    "논문 실적",
    "논문 순위",
    "실적 순위",
    "합격 가능성",
    "합격 확률",
    "가장 합격하기 쉬운",
    "장학금 지급 금액",
    "대기업 취업 가능성",
]

UNSUPPORTED_KAIST_DEPARTMENT_KEYWORDS = [
    "전산학부",
    "전기및전자공학부",
    "전기 및 전자공학부",
    "기계공학과",
    "항공우주공학과",
    "건설및환경공학과",
    "건설 및 환경공학과",
    "바이오및뇌공학과",
    "바이오 및 뇌공학과",
    "생명화학공학과",
    "신소재공학과",
    "원자력및양자공학과",
    "원자력 및 양자공학과",
    "산업및시스템공학과",
    "산업 및 시스템공학과",
    "산업디자인학과",
    "수리과학과",
    "물리학과",
    "화학과",
    "생명과학과",
    "뇌인지과학과",
    "기술경영학부",
    "경영공학부",
    "디지털인문사회과학부",
    "문화기술대학원",
    "과학기술정책대학원",
    "의과학대학원",
    "문술미래전략대학원",
    "녹색성장지속가능대학원",
    "서울대학교",
    "서울대",
    "POSTECH",
    "포스텍",
    "연세대",
    "고려대",
    "성균관대",
]

OFF_TOPIC_KEYWORDS = [
    "오늘 날씨",
    "내일 날씨",
    "맛집",
    "주식",
    "코인",
    "비트코인",
    "번역해줘",
    "파이썬 코드 짜줘",
    "자기소개서 써줘",
]


KAIST_OFFICIAL_URL = "https://www.kaist.ac.kr/kr/"
KAIST_ADMISSION_URL = "https://admission.kaist.ac.kr/home"


# ============================================================
# 4. Intent examples
# ============================================================

INTENT_EXAMPLES = [
    IntentExample("AI컴퓨팅학과 석사 지원 자격 알려줘", "admission_info"),
    IntentExample("AX학과 입학 요건 알려줘", "admission_info"),
    IntentExample("AI시스템학과 대학원 모집 일정 알려줘", "admission_info"),
    IntentExample("AI미래학과 제출 서류 알려줘", "admission_info"),
    IntentExample("입학 조건 알려줘", "admission_info", "missing_department"),

    IntentExample("AI컴퓨팅학과 교과목 목록 보여줘", "course_info"),
    IntentExample("AI시스템학과 커리큘럼 알려줘", "course_info"),
    IntentExample("AX학과 수업 과목 설명해줘", "course_info"),
    IntentExample("교과목 알려줘", "course_info", "missing_department"),

    IntentExample("AI컴퓨팅학과 교수진 알려줘", "person_info"),
    IntentExample("AX학과 교수 이메일 알려줘", "person_info"),
    IntentExample("AI미래학과 연구실 알려줘", "person_info"),
    IntentExample("지도교수 찾고 싶어", "person_info", "missing_department"),

    IntentExample("AI시스템학과 학과 사무실 전화번호", "office_contact_info"),
    IntentExample("AI컴퓨팅학과 연락처 알려줘", "office_contact_info"),
    IntentExample("AI시스템학과의 연락처가 문서에 나와 있어?", "office_contact_info"),
    IntentExample("AX학과 문의처 알려줘", "office_contact_info"),
    IntentExample("AI미래학과 이메일 주소 알려줘", "office_contact_info"),
    IntentExample("KAIST 학과 사무실 전화번호 알려줘", "office_contact_info"),

    IntentExample("AI컴퓨팅학과 설명회 일정 알려줘", "event_info"),
    IntentExample("AX학과 공지사항 알려줘", "event_info"),
    IntentExample("학과 입시설명회 정보 알려줘", "event_info", "missing_department"),

    IntentExample("AI시스템학과 자료 다운로드 링크", "asset_or_link_info"),
    IntentExample("AX학과 브로슈어 pdf", "asset_or_link_info"),

    IntentExample("AI대학 학과별 홈페이지 URL을 정리해줘", "department_homepage_info"),
    IntentExample("AI컴퓨팅학과 홈페이지 알려줘", "department_homepage_info"),
    IntentExample("AX학과 사이트 알려줘", "department_homepage_info"),

    IntentExample("AI컴퓨팅학과 소개해줘", "department_overview"),
    IntentExample("AI시스템학과 특징 알려줘", "department_overview"),
    IntentExample("AX학과는 어떤 학과야", "department_overview"),
    IntentExample("AI미래학과는 어떤 인재를 양성하려고 해?", "department_overview"),
    IntentExample("AI컴퓨팅학과 교육목표 알려줘", "department_overview"),
    IntentExample("AX학과는 어떤 인재를 원해?", "department_overview"),

    IntentExample("AI컴퓨팅학과와 AX학과를 비교해줘", "comparison_info"),
    IntentExample("AI대학 학과들을 표 형식으로 비교해줘", "comparison_info"),
    IntentExample("AI시스템학과와 AI미래학과 차이를 알려줘", "comparison_info"),

    IntentExample("나는 AI 서비스 적용에 관심이 있는데 어떤 학과가 맞아?", "recommendation_info"),
    IntentExample("산업 현장에 AI를 적용하고 싶은데 어떤 학과가 적합해?", "recommendation_info"),
    IntentExample("소프트웨어 쪽에 관심이 있으면 어떤 학과를 보면 좋을까?", "recommendation_info"),
    IntentExample("미래 AI 기술과 사회 변화에 관심이 있는데 어떤 학과가 맞아?", "recommendation_info"),

    IntentExample("AI컴퓨팅학과의 졸업 요건이 문서에 나와 있어?", "requirement_info"),
    IntentExample("AI대학 학과별 이수 요건을 비교해줘", "requirement_info"),
    IntentExample("AI대학 논문 제출 요건 알려줘", "requirement_info"),

    IntentExample("카이스트 주소 알려줘", "kaist_profile_info"),
    IntentExample("KAIST 대표 번호 알려줘", "kaist_profile_info"),
    IntentExample("카이스트 전화 알려줘", "kaist_profile_info"),
    IntentExample("카이스트 설립일 알려줘", "kaist_profile_info"),
    IntentExample("한국과학기술원 영문명 알려줘", "kaist_profile_info"),

    IntentExample("카이스트 재학생 수 알려줘", "kaist_statistics_info"),
    IntentExample("KAIST 졸업생 몇 명이야", "kaist_statistics_info"),
    IntentExample("카이스트 교직원 수 알려줘", "kaist_statistics_info"),

    IntentExample("카이스트 공식 홈페이지 링크", "kaist_link_info"),
    IntentExample("KAIST 입학처 링크 알려줘", "kaist_link_info"),
    IntentExample("카이스트 캠퍼스맵 보여줘", "kaist_link_info"),

    IntentExample("전산학부 교수진 알려줘", "general_info", "unsupported_kaist_department"),
    IntentExample("기계공학과 입학 정보 알려줘", "general_info", "unsupported_kaist_department"),

    IntentExample("오늘 날씨 알려줘", "general_info", "off_topic"),
    IntentExample("파이썬 코드 짜줘", "general_info", "off_topic"),
    IntentExample("맛집 추천해줘", "general_info", "off_topic"),
]


# ============================================================
# 5. Intent rules
# 순서 중요:
# requirement / recommendation / comparison / homepage를 먼저 검사해야 함.
# ============================================================

INTENT_RULES = [
    IntentRule(
        intent="requirement_info",
        content_type="requirement",
        description="졸업/수료/이수/논문 요건 질문",
        keywords=[
            "졸업 요건",
            "졸업요건",
            "수료 요건",
            "수료요건",
            "이수 요건",
            "이수요건",
            "논문 제출",
            "논문제출",
            "학위논문",
            "졸업학점",
            "수료학점",
            "필수학점",
            "졸업 조건",
            "수료 조건",
        ],
        vector_search_terms="졸업 요건 수료 요건 이수 요건 논문 제출 학위논문 졸업학점 수료학점",
        sql_table_hint="department_requirement",
        sql_task_hint="requirement_lookup",
    ),
    IntentRule(
        intent="department_homepage_info",
        content_type="department_homepage",
        description="학과별 대표 홈페이지/URL 질문",
        keywords=[
            "학과별 홈페이지",
            "대표 홈페이지",
            "홈페이지 URL",
            "홈페이지 url",
            "홈페이지 링크",
            "학과 홈페이지",
            "학과별 URL",
            "학과별 url",
            "사이트 주소",
            "사이트 알려줘",
            "학과 사이트",
        ],
        vector_search_terms="학과별 대표 홈페이지 URL 사이트 링크",
        sql_table_hint="department_homepage",
        sql_task_hint="department_homepage_lookup",
    ),
    IntentRule(
        intent="recommendation_info",
        content_type=None,
        description="관심사 기반 학과 추천 질문",
        keywords=[
            "어떤 학과가 맞아",
            "어떤 학과가 적합",
            "어떤 학과를 보면",
            "어떤 학과 정보를 먼저",
            "추천",
            "관심이 있어",
            "관심 있는데",
            "서비스 적용",
            "산업 현장",
            "현장 적용",
            "소프트웨어 쪽",
            "하드웨어보다",
            "사회 변화",
            "기획과 개발",
            "적합해",
            "맞을까",
            "맞아",
        ],
        vector_search_terms="학과 추천 관심사 적합 산업 현장 서비스 적용 소프트웨어 미래 사회 변화 AI 전환",
        sql_table_hint=None,
        sql_task_hint=None,
    ),
    IntentRule(
        intent="comparison_info",
        content_type=None,
        description="학과 비교 질문",
        keywords=[
            "비교",
            "차이",
            "차이점",
            "표 형식",
            "표로",
            "공통점",
            "다른 점",
            "비슷한 점",
        ],
        vector_search_terms="학과 비교 차이 특징 교육 목표 교과목 교수진 입학 정보",
        sql_table_hint=None,
        sql_task_hint=None,
    ),
    IntentRule(
        intent="kaist_statistics_info",
        content_type="kaist_statistics",
        description="KAIST 통계 정보 질문",
        keywords=[
            "통계",
            "재학생",
            "졸업생",
            "교직원",
            "학생 수",
            "학생수",
            "인원",
            "몇 명",
            "몇명",
            "statistics",
        ],
        vector_search_terms="KAIST 통계 재학생 졸업생 교직원 학생 수 인원",
        sql_table_hint="kaist_statistics",
        sql_task_hint="kaist_statistics_lookup",
    ),
    IntentRule(
        intent="kaist_link_info",
        content_type="link",
        description="KAIST 공식 링크 질문",
        keywords=[
            "공식 홈페이지",
            "카이스트 홈페이지",
            "KAIST 홈페이지",
            "kaist homepage",
            "입학처",
            "캠퍼스맵",
            "셔틀버스",
            "도서관",
            "학사일정",
        ],
        vector_search_terms="KAIST 공식 홈페이지 입학처 캠퍼스맵 셔틀버스 도서관 학사일정 링크 URL",
        sql_table_hint="kaist_links",
        sql_task_hint="kaist_link_lookup",
    ),
    IntentRule(
        intent="kaist_profile_info",
        content_type="kaist_profile",
        description="KAIST 기본 정보 질문",
        keywords=[
            "카이스트 주소",
            "KAIST 주소",
            "카이스트 대표 번호",
            "KAIST 대표 번호",
            "카이스트 전화번호",
            "KAIST 전화번호",
            "대표 번호",
            "대표번호",
            "팩스",
            "약자",
            "영문약자",
            "설립일",
            "창립일",
            "영문명",
            "학교명",
            "설립이념",
            "색상",
            "카이스트 기본 정보",
            "KAIST 기본 정보",
        ],
        vector_search_terms="KAIST 기본정보 학교명 영문명 창립일 설립일 주소 대표 번호 팩스 설립이념 색상",
        sql_table_hint="kaist_profile",
        sql_task_hint="kaist_profile_lookup",
    ),
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
        description="학과 사무실/전화번호/위치/연락처 질문",
        keywords=[
            "학과사무실",
            "학과 사무실",
            "사무실",
            "행정실",
            "전화번호",
            "전화",
            "연락처",
            "문의처",
            "문의",
            "연락",
            "이메일 주소",
            "메일 주소",
            "사무국",
            "행정 담당",
            "위치",
            "건물",
            "office",
            "contact",
            "phone",
            "location",
        ],
        vector_search_terms="학과사무실 전화번호 위치 웹사이트 연락처 행정실 문의처",
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
            "제출 서류",
            "제출서류",
            "admission",
            "apply",
            "eligibility",
        ],
        vector_search_terms="대학원 입학 지원 자격 모집 전형 석사 박사 석박사 통합과정 제출서류",
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
            "자료",
            "다운로드",
            "첨부파일",
            "파일",
            "PDF",
            "pdf",
            "브로슈어",
        ],
        vector_search_terms="링크 URL 자료 다운로드 첨부파일 PDF 브로슈어",
        sql_table_hint="assets",
        sql_task_hint="asset_lookup",
    ),
    IntentRule(
        intent="department_overview",
        content_type=None,
        description="학과 소개/목표/인재양성 질문",
        keywords=[
            "인재",
            "양성",
            "인재상",
            "교육목표",
            "교육 목표",
            "목표 인재",
            "어떤 사람",
            "어떤 학생",
            "학과 목표",
            "학과 소개",
            "소개",
            "어떤 학과",
            "무슨 학과",
            "특징",
            "비전",
            "목표",
            "개요",
            "방향",
        ],
        vector_search_terms="학과 소개 개요 특징 비전 목표 인재 양성 교육목표 교육 연구",
        sql_table_hint=None,
        sql_task_hint=None,
    ),
]


# ============================================================
# 6. QuestionAnalyzer
# ============================================================

class QuestionAnalyzer:
    def __init__(
        self,
        departments: list[DepartmentInfo] | None = None,
        intent_rules: list[IntentRule] | None = None,
        intent_examples: list[IntentExample] | None = None,
    ) -> None:
        self.departments = departments or DEPARTMENTS
        self.intent_rules = intent_rules or INTENT_RULES
        self.intent_examples = intent_examples or INTENT_EXAMPLES

    # ------------------------------------------------------------
    # public API
    # ------------------------------------------------------------

    def analyze(
        self,
        question: str,
        previous_department_code: str | None = None,
    ) -> QueryAnalysis:
        original_question = question or ""
        normalized_question = self._normalize_question(original_question)

        matched_departments = self._find_departments(normalized_question)
        unsupported_department_name = self._find_unsupported_department(
            normalized_question
        )

        scope_resolved = self._is_ai_college_scope(normalized_question)

        department = self._select_primary_department(
            matched_departments=matched_departments,
            previous_department_code=previous_department_code,
            scope_resolved=scope_resolved,
        )

        department_name = department.name if department else None
        department_code = department.code if department else None

        department_names = [dept.name for dept in matched_departments]
        department_codes = [dept.code for dept in matched_departments]
        is_multi_department = len(matched_departments) >= 2

        intent_rule, matched_keywords = self._find_intent_rule(
            normalized_question
        )

        if intent_rule is None:
            intent_rule = IntentRule(
                intent="general_info",
                content_type=None,
                description="일반 정보 질문",
                keywords=[],
                vector_search_terms="",
                sql_table_hint=None,
                sql_task_hint=None,
            )

        ambiguity_type = self._detect_ambiguity_type(
            normalized_question=normalized_question,
            intent_rule=intent_rule,
            unsupported_department_name=unsupported_department_name,
        )

        missing_fields = self._find_missing_fields(
            intent=intent_rule.intent,
            content_type=intent_rule.content_type,
            department_code=department_code,
            scope_resolved=scope_resolved,
            is_multi_department=is_multi_department,
        )

        if ambiguity_type == "unsupported_kaist_department":
            route = "clarify"
            route_reason = "현재 수집 범위 밖의 학과 또는 외부 대학 질문입니다."
        elif ambiguity_type == "unsupported_fact":
            route = "clarify"
            route_reason = "현재 수집 데이터에 없는 고위험 사실 질문입니다."
        elif ambiguity_type == "off_topic":
            route = "clarify"
            route_reason = "KAIST AI College RAG 범위 밖의 질문입니다."
        elif missing_fields:
            route = "clarify"
            route_reason = "질문을 처리하는 데 필요한 정보가 부족합니다."
        else:
            route, route_reason = self._decide_route(intent_rule)

        is_ambiguous = route == "clarify" or bool(missing_fields)

        clarifying_message = None
        if is_ambiguous:
            clarifying_message = self._build_clarifying_message(
                intent=intent_rule.intent,
                ambiguity_type=ambiguity_type,
                missing_fields=missing_fields,
                unsupported_department_name=unsupported_department_name,
            )

        rewritten_question = self._build_rewritten_question(
            normalized_question=normalized_question,
            intent_rule=intent_rule,
            department=department,
            matched_departments=matched_departments,
            scope_resolved=scope_resolved,
        )

        metadata_filter = self._build_metadata_filter(
            intent_rule=intent_rule,
            department=department,
            is_multi_department=is_multi_department,
        )

        sql_conditions = self._build_sql_conditions(
            department=department,
            matched_departments=matched_departments,
            intent_rule=intent_rule,
            scope_resolved=scope_resolved,
        )

        needs_sql = route in {"sql", "hybrid"}
        needs_vector = route in {"vector", "hybrid"}

        return QueryAnalysis(
            original_question=original_question,
            normalized_question=normalized_question,
            route=route,
            route_reason=route_reason,
            display_question=normalized_question,
            rewritten_question=rewritten_question,
            department_name=department_name,
            department_code=department_code,
            department_names=department_names,
            department_codes=department_codes,
            is_multi_department=is_multi_department,
            unsupported_department_name=unsupported_department_name,
            intent=intent_rule.intent,
            intent_description=intent_rule.description,
            content_type=intent_rule.content_type,
            metadata_filter=metadata_filter,
            sql_table_hint=intent_rule.sql_table_hint,
            sql_task_hint=intent_rule.sql_task_hint,
            sql_conditions=sql_conditions,
            needs_sql=needs_sql,
            needs_vector=needs_vector,
            is_ambiguous=is_ambiguous,
            ambiguity_type=ambiguity_type,
            missing_fields=missing_fields,
            clarifying_message=clarifying_message,
            matched_keywords=matched_keywords,
        )

    # ------------------------------------------------------------
    # normalize / matching
    # ------------------------------------------------------------

    def _normalize_question(self, question: str) -> str:
        text = str(question or "")
        text = text.replace("\r\n", " ").replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _find_departments(self, question: str) -> list[DepartmentInfo]:
        lowered_question = question.lower()
        matched: list[DepartmentInfo] = []

        for department in self.departments:
            for keyword in department.keywords:
                keyword_lower = keyword.lower()

                if keyword_lower and keyword_lower in lowered_question:
                    matched.append(department)
                    break

        # 순서 보존 + 중복 제거
        deduped: list[DepartmentInfo] = []
        seen_codes: set[str] = set()

        for department in matched:
            if department.code in seen_codes:
                continue

            deduped.append(department)
            seen_codes.add(department.code)

        return deduped

    def _select_primary_department(
        self,
        matched_departments: list[DepartmentInfo],
        previous_department_code: str | None,
        scope_resolved: bool,
    ) -> DepartmentInfo | None:
        if len(matched_departments) == 1:
            return matched_departments[0]

        # 비교 질문처럼 여러 학과가 명시된 경우 primary는 None으로 둔다.
        if len(matched_departments) >= 2:
            return None

        # 전체 학과 범위 질문이면 특정 학과를 선택하지 않는다.
        if scope_resolved:
            return None

        # 후속 질문에서 이전 학과가 있으면 사용한다.
        if previous_department_code:
            return self._department_by_code(previous_department_code)

        return None

    def _department_by_code(self, code: str | None) -> DepartmentInfo | None:
        if not code:
            return None

        for department in self.departments:
            if department.code == code:
                return department

        return None

    def _find_unsupported_department(self, question: str) -> str | None:
        lowered_question = question.lower()

        for keyword in UNSUPPORTED_KAIST_DEPARTMENT_KEYWORDS:
            if keyword.lower() in lowered_question:
                return keyword

        return None

    def _is_ai_college_scope(self, question: str) -> bool:
        lowered_question = question.lower()

        return any(
            keyword.lower() in lowered_question
            for keyword in AI_COLLEGE_SCOPE_KEYWORDS
        )

    def _contains_any(self, text: str, keywords: list[str]) -> bool:
        lowered_text = text.lower()

        return any(keyword.lower() in lowered_text for keyword in keywords)

    # ------------------------------------------------------------
    # intent detection
    # ------------------------------------------------------------

    def _find_intent_rule(
        self,
        normalized_question: str,
    ) -> tuple[IntentRule | None, list[str]]:
        lowered_question = normalized_question.lower()

        # 1. 졸업/수료/이수/논문 요건은 overview보다 먼저 잡는다.
        if self._contains_any(
            lowered_question,
            [
                "졸업 요건",
                "졸업요건",
                "수료 요건",
                "수료요건",
                "이수 요건",
                "이수요건",
                "논문 제출",
                "논문제출",
                "학위논문",
                "졸업학점",
                "수료학점",
                "필수학점",
                "졸업 조건",
                "수료 조건",
            ],
        ):
            rule = self._get_intent_rule_by_intent("requirement_info")
            if rule:
                return rule, ["requirement"]

        # 2. 추천 질문은 "어떤 학과" 때문에 missing_department로 빠지면 안 된다.
        if self._is_interest_based_recommendation_question(lowered_question):
            rule = self._get_intent_rule_by_intent("recommendation_info")
            if rule:
                return rule, ["recommendation"]

        # 3. 비교 질문은 department_overview가 아니라 comparison_info로 보낸다.
        if self._is_compare_question(lowered_question):
            rule = self._get_intent_rule_by_intent("comparison_info")
            if rule:
                return rule, ["comparison"]

        # 4. 학과별 홈페이지/URL은 asset이 아니라 department_homepage로 보낸다.
        if self._contains_any(
            lowered_question,
            [
                "학과별 홈페이지",
                "대표 홈페이지",
                "홈페이지 url",
                "홈페이지 URL",
                "홈페이지 링크",
                "학과 홈페이지",
                "학과별 url",
                "학과별 URL",
                "사이트 주소",
                "사이트 알려줘",
                "학과 사이트",
            ],
        ):
            rule = self._get_intent_rule_by_intent("department_homepage_info")
            if rule:
                return rule, ["department_homepage"]

        # 5. 홈페이지 단독 질문 처리
        if "홈페이지" in lowered_question or "사이트" in lowered_question:
            # KAIST 전체 홈페이지
            if any(
                keyword in lowered_question
                for keyword in ["kaist", "카이스트", "한국과학기술원"]
            ) and not any(
                keyword in lowered_question
                for keyword in ["학과별", "학과", "ai컴퓨팅", "ai시스템", "ax", "ai미래"]
            ):
                kaist_link_rule = self._get_intent_rule_by_intent("kaist_link_info")

                if kaist_link_rule:
                    return kaist_link_rule, ["카이스트 홈페이지"]

            # 교수 홈페이지는 person_info
            person_specific_keywords = [
                "교수",
                "교수진",
                "구성원",
                "연구실",
                "지도교수",
                "faculty",
                "professor",
            ]

            if any(
                keyword in lowered_question
                for keyword in person_specific_keywords
            ):
                person_rule = self._get_intent_rule_by_intent("person_info")

                if person_rule:
                    return person_rule, ["교수 홈페이지"]

            homepage_rule = self._get_intent_rule_by_intent(
                "department_homepage_info"
            )

            if homepage_rule:
                return homepage_rule, ["홈페이지"]

        # 6. 일반 intent rule 매칭
        for rule in self.intent_rules:
            matched_keywords = [
                keyword
                for keyword in rule.keywords
                if keyword.lower() in lowered_question
            ]

            if matched_keywords:
                return rule, matched_keywords

        return None, []

    def _get_intent_rule_by_intent(
        self,
        intent: IntentType,
    ) -> IntentRule | None:
        for rule in self.intent_rules:
            if rule.intent == intent:
                return rule

        return None

    def _is_compare_question(self, question: str) -> bool:
        compare_keywords = [
            "비교",
            "차이",
            "차이점",
            "표 형식",
            "표로",
            "공통점",
            "다른 점",
            "비슷한 점",
            "vs",
            "versus",
        ]

        return self._contains_any(question, compare_keywords)

    def _is_interest_based_recommendation_question(self, question: str) -> bool:
        interest_keywords = [
            "관심이 있어",
            "관심 있는데",
            "관심 있어",
            "희망",
            "하고 싶",
            "배우고 싶",
            "진로",
            "서비스 적용",
            "산업 현장",
            "현장 적용",
            "소프트웨어 쪽",
            "하드웨어보다",
            "사회 변화",
            "기획과 개발",
            "어떤 학과가 맞",
            "어떤 학과가 적합",
            "어떤 학과를 보면",
            "어떤 학과 정보를 먼저",
            "추천",
            "맞을까",
            "적합해",
        ]

        has_interest = self._contains_any(question, interest_keywords)

        has_department_choice = self._contains_any(
            question,
            [
                "어떤 학과",
                "무슨 학과",
                "어느 학과",
                "학과가 맞",
                "학과가 적합",
                "학과를 보면",
                "추천",
            ],
        )

        return has_interest and has_department_choice

    # ------------------------------------------------------------
    # ambiguity / missing
    # ------------------------------------------------------------

    def _detect_ambiguity_type(
        self,
        normalized_question: str,
        intent_rule: IntentRule,
        unsupported_department_name: str | None,
    ) -> AmbiguityType | None:
        lowered_question = normalized_question.lower()

        if unsupported_department_name:
            return "unsupported_kaist_department"

        if self._contains_any(lowered_question, UNSUPPORTED_FACT_KEYWORDS):
            return "unsupported_fact"

        if self._contains_any(lowered_question, OFF_TOPIC_KEYWORDS):
            return "off_topic"

        if lowered_question in {"다 알려줘", "전체 정보 알려줘", "정보 알려줘"}:
            return "too_broad"

        if intent_rule.intent == "general_info":
            unclear_keywords = ["거기", "그 학과", "그거", "그쪽"]

            if self._contains_any(lowered_question, unclear_keywords):
                return "unclear_reference"

        return None

    def _find_missing_fields(
        self,
        intent: IntentType,
        content_type: ContentType | None,
        department_code: str | None,
        scope_resolved: bool,
        is_multi_department: bool,
    ) -> list[str]:
        missing_fields: list[str] = []

        # 추천/비교/홈페이지/요건은 학과가 없어도 전체 범위로 처리 가능하다.
        if intent in {
            "recommendation_info",
            "comparison_info",
            "department_homepage_info",
            "requirement_info",
        }:
            return missing_fields

        # KAIST 전체 정보는 학과 필요 없음.
        if intent in {
            "kaist_profile_info",
            "kaist_statistics_info",
            "kaist_link_info",
        }:
            return missing_fields

        # 전체 학과 범위 질문은 학과 필요 없음.
        if scope_resolved:
            return missing_fields

        # 여러 학과가 명시된 비교성 질문은 학과 필요 없음.
        if is_multi_department:
            return missing_fields

        if content_type in {"course", "person", "admission", "event"}:
            if department_code is None:
                missing_fields.append("department")

        if intent == "department_overview" and department_code is None:
            missing_fields.append("department")

        return missing_fields

    def _build_clarifying_message(
        self,
        intent: IntentType,
        ambiguity_type: AmbiguityType | None,
        missing_fields: list[str],
        unsupported_department_name: str | None,
    ) -> str:
        if ambiguity_type == "unsupported_kaist_department":
            return (
                f"현재 수집된 데이터는 KAIST AI College 관련 4개 학과"
                f"(AI컴퓨팅학과, AI시스템학과, AX학과, AI미래학과)를 중심으로 합니다. "
                f"'{unsupported_department_name}' 정보는 현재 수집 범위에서 확인하기 어렵습니다."
            )

        if ambiguity_type == "unsupported_fact":
            return (
                "현재 수집 자료에는 경쟁률, 등록금, 취업률, 연봉, 합격 가능성처럼 "
                "변동성이 크거나 공식 근거가 필요한 정보가 충분히 포함되어 있지 않습니다. "
                "해당 정보는 KAIST 공식 홈페이지 또는 입학처에서 확인하는 것이 안전합니다."
            )

        if ambiguity_type == "off_topic":
            return (
                "이 챗봇은 KAIST AI College의 입학, 학과 소개, 교수진, 교과목, 행사, "
                "연락처 정보를 안내하는 용도입니다. KAIST AI College 관련 질문으로 다시 입력해주세요."
            )

        if "department" in missing_fields:
            if intent == "course_info":
                return (
                    "어느 학과의 교과목 정보를 원하시나요? "
                    "AI컴퓨팅학과, AI시스템학과, AX학과, AI미래학과 중에서 선택해주세요."
                )

            if intent == "person_info":
                return (
                    "어느 학과의 교수진 정보를 원하시나요? "
                    "AI컴퓨팅학과, AI시스템학과, AX학과, AI미래학과 중에서 선택해주세요."
                )

            if intent == "admission_info":
                return (
                    "어느 학과의 입학 정보를 원하시나요? "
                    "AI컴퓨팅학과, AI시스템학과, AX학과, AI미래학과 중에서 선택해주세요."
                )

            if intent == "department_overview":
                return (
                    "어느 학과의 소개 정보를 원하시나요? "
                    "AI컴퓨팅학과, AI시스템학과, AX학과, AI미래학과 중에서 선택하거나 "
                    "'전체 학과'라고 입력해주세요."
                )

        return "질문을 조금 더 구체적으로 입력해주세요."

    # ------------------------------------------------------------
    # route / query / filters
    # ------------------------------------------------------------

    def _decide_route(self, intent_rule: IntentRule) -> tuple[RouteType, str]:
        if intent_rule.intent in {
            "kaist_profile_info",
            "kaist_statistics_info",
            "kaist_link_info",
            "course_info",
            "person_info",
            "office_contact_info",
            "asset_or_link_info",
            "department_homepage_info",
            "requirement_info",
        }:
            return "sql", "정확한 정형 데이터 조회가 적합한 질문입니다."

        if intent_rule.intent in {
            "admission_info",
            "event_info",
        }:
            return "hybrid", "정형 데이터와 문서 설명 근거가 함께 필요한 질문입니다."

        if intent_rule.intent in {
            "department_overview",
            "recommendation_info",
            "comparison_info",
        }:
            return "vector", "문서 내용과 설명 근거가 중요한 질문입니다."

        return "vector", "일반 문서 검색으로 처리합니다."

    def _build_rewritten_question(
        self,
        normalized_question: str,
        intent_rule: IntentRule,
        department: DepartmentInfo | None,
        matched_departments: list[DepartmentInfo],
        scope_resolved: bool,
    ) -> str:
        parts = [normalized_question]

        if matched_departments:
            dept_names = " ".join(dept.name for dept in matched_departments)
            parts.append(f"관련 학과: {dept_names}")
        elif department:
            parts.append(f"관련 학과: {department.name}")
        elif scope_resolved:
            parts.append("관련 범위: KAIST AI College 전체 학과")

        if intent_rule.vector_search_terms:
            parts.append(f"검색 확장어: {intent_rule.vector_search_terms}")

        return "\n".join(parts)

    def _build_metadata_filter(
        self,
        intent_rule: IntentRule,
        department: DepartmentInfo | None,
        is_multi_department: bool,
    ) -> dict[str, Any] | None:
        metadata_filter: dict[str, Any] = {}

        # 여러 학과 비교는 retriever에서 학과별 검색을 해야 하므로 여기서는 dept 필터를 걸지 않는다.
        if department and not is_multi_department:
            metadata_filter["dept"] = department.code

        # recommendation/comparison/overview는 현재 vectorstore에 department_profile이 없을 수 있으므로
        # content_type을 강하게 걸지 않는다.
        if intent_rule.intent not in {
            "recommendation_info",
            "comparison_info",
            "department_overview",
        }:
            if intent_rule.content_type:
                metadata_filter["content_type"] = intent_rule.content_type

        return metadata_filter or None

    def _build_sql_conditions(
        self,
        department: DepartmentInfo | None,
        matched_departments: list[DepartmentInfo],
        intent_rule: IntentRule,
        scope_resolved: bool,
    ) -> dict[str, Any]:
        conditions: dict[str, Any] = {}

        if department:
            conditions["dept"] = department.code
            conditions["dept_name"] = department.name

        if matched_departments:
            conditions["dept_codes"] = [dept.code for dept in matched_departments]
            conditions["dept_names"] = [dept.name for dept in matched_departments]

        if scope_resolved:
            conditions["scope"] = "ai_college"

        if intent_rule.content_type:
            conditions["content_type"] = intent_rule.content_type

        return conditions


# ============================================================
# 7. 간단 수동 테스트
# ============================================================

if __name__ == "__main__":
    analyzer = QuestionAnalyzer()

    questions = [
        "AI미래학과는 어떤 인재를 양성하려고 해?",
        "AI컴퓨팅학과의 연락처가 문서에 나와 있어?",
        "AI대학 학과별 홈페이지 URL을 정리해줘.",
        "AI컴퓨팅학과와 AX학과를 비교해줘.",
        "나는 AI 서비스 적용에 관심이 있는데 어떤 학과가 맞아?",
        "AI컴퓨팅학과의 졸업 요건이 문서에 나와 있어?",
        "AI시스템학과의 교육과정을 알려줘.",
        "KAIST 대표 번호 알려줘.",
    ]

    for question in questions:
        analysis = analyzer.analyze(question)
        print("=" * 100)
        print("Q:", question)
        print("route:", analysis.route)
        print("intent:", analysis.intent)
        print("dept:", analysis.department_code)
        print("dept_codes:", analysis.department_codes)
        print("content_type:", analysis.content_type)
        print("sql_task:", analysis.sql_task_hint)
        print("needs_sql:", analysis.needs_sql)
        print("needs_vector:", analysis.needs_vector)
        print("missing:", analysis.missing_fields)
        print("clarify:", analysis.clarifying_message)