from html import escape

import streamlit as st

from components.styles import load_css
from components.layout import render_topbar, render_page_header, render_info_card, render_back_home
from data.demo_knowledge import get_departments, get_representative_courses, get_department_heads

st.set_page_config(
    page_title="Departments | KAIST AI RAG Guide",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

load_css()
render_topbar()
render_back_home()

render_page_header(
    kicker="DEPARTMENTS & RESEARCH AREAS",
    title="Departments 소개",
    description="KAIST AI College의 학과, 연구 분야, 교수진, 교과목 데이터를 사용자 친화적인 카드형 화면으로 재구성했습니다.",
)

st.markdown('<div class="section-title">Department Overview</div>', unsafe_allow_html=True)
departments = get_departments()

DEPT_ICONS = {
    "AI컴퓨팅학과": "🖥️",
    "AI시스템학과": "⚙️",
    "AI미래학과": "🔭",
    "AX학과": "🔄",
}

if departments:
    col_a, col_b = st.columns(2, gap="medium")

    for idx, dept in enumerate(departments):
        col = col_a if idx % 2 == 0 else col_b
        dept_name = escape(str(dept.get("dept_name", "Department")))
        icon = DEPT_ICONS.get(dept.get("dept_name", ""), "🎓")
        summary = escape(str(dept.get("summary", "소개 데이터가 준비 중입니다.")))
        source_url = str(dept.get("source_url", "")).strip()

        link = (
            f'<a href="{escape(source_url)}" target="_blank" class="card-link">홈페이지 바로가기 →</a>'
            if source_url
            else ""
        )

        with col:
            st.markdown(
                f"""
                <div class="info-card start-card department-overview-card">
                    <div class="department-icon">{icon}</div>
                    <h3>{dept_name}</h3>
                    <p>{summary}</p>
                    <div class="card-link-wrap">{link}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.info("학과 소개 데이터를 찾을 수 없습니다.")

st.markdown('<div class="section-title">Representative Faculty</div>', unsafe_allow_html=True)
heads = get_department_heads()

if heads:
    cols = st.columns(len(heads), gap="medium")

    for idx, person in enumerate(heads):
        with cols[idx]:
            name = escape(str(person.get("name_ko") or person.get("name") or ""))
            dept_name = escape(str(person.get("dept_name", "")))
            homepage = str(person.get("homepage", "")).strip()
            role_label = escape(str(person.get("role_normalized") or person.get("role") or "학과장"))

            title = (
                f'<a href="{escape(homepage)}" target="_blank">{name}</a>'
                if homepage
                else name
            )

            st.markdown(
                f"""
                <div class="info-card start-card faculty-chair-card">
                    <div class="faculty-dept-label">{dept_name}</div>
                    <h3>{title}</h3>
                    <p>{role_label}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.info("교수진 정보를 확인할 수 없습니다.")

st.markdown('<div class="section-title">Representative Courses</div>', unsafe_allow_html=True)
courses = get_representative_courses(limit=8)

if courses:
    st.markdown('<div class="course-list-wrap">', unsafe_allow_html=True)

    for course in courses:
        dept_name = escape(str(course.get("dept_name", "")))
        course_code = escape(str(course.get("course_code", "")))
        course_name = escape(str(course.get("course_name", "")))
        track_name = escape(str(course.get("track_name", "")))
        course_type = escape(str(course.get("course_type", "")))
        source_url = str(course.get("source_url", "")).strip()

        course_title = f"{course_name} ({course_code})".strip()
        meta_parts = [part for part in [dept_name, track_name, course_type] if part]
        meta_html = " · ".join(meta_parts)

        if source_url:
            title_html = (
                f'<a href="{escape(source_url)}" target="_blank" class="course-title">'
                f'{course_title}'
                f'</a>'
            )
        else:
            title_html = f'<span class="course-title">{course_title}</span>'

        st.markdown(
            f"""
            <div class="info-card compact-course-card">
                <div class="course-line">
                    {title_html}
                    <span class="course-meta">· {meta_html}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("교과목 데이터를 찾을 수 없습니다.")

st.markdown('<div class="section-title">How This Connects to RAG</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2, gap="medium")

with c1:
    render_info_card("검색 대상 문서", "학과 소개, 교수진 정보, 교과목 안내, 연구 키워드 데이터는 RAG 검색의 문서 후보로 활용됩니다.")

with c2:
    render_info_card("사용자 질문 예시", "예비 지원자는 “NLP 연구를 하는 교수님은?”, “AI시스템 관련 과목은?”처럼 질문할 수 있습니다.")
