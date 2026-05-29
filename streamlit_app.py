import base64
from pathlib import Path

import streamlit as st

from components.styles import load_css


st.set_page_config(
    page_title="KAIST AI College RAG Guide",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

load_css()


def html(markup: str):
    st.markdown(markup, unsafe_allow_html=True)


def image_to_base64(image_path: str) -> str:
    """
    로컬 이미지 파일을 base64 문자열로 변환한다.
    Streamlit HTML 내부에서 상대경로 이미지가 깨지는 문제를 방지하기 위한 함수이다.
    """
    path = Path(image_path)

    if not path.exists():
        st.error(f"이미지 파일을 찾을 수 없습니다: {image_path}")
        return ""

    return base64.b64encode(path.read_bytes()).decode("utf-8")


kaist_img_base64 = image_to_base64("assets/kaist.jpg")

if kaist_img_base64:
    kaist_img_tag = (
        f'<img src="data:image/jpeg;base64,{kaist_img_base64}" '
        f'alt="KAIST AI College image">'
    )
else:
    kaist_img_tag = '<div class="image-fallback">KAIST Image Not Found</div>'


html(
    '<div class="topbar">'
    '<div class="brand">'
    '<div class="brand-mark">AI</div>'
    '<div>'
    '<div class="brand-title">KAIST AI College<br>RAG Guide</div>'
    '<div class="brand-subtitle">Document-grounded guide for prospective students</div>'
    '</div>'
    '</div>'
    '<div class="demo-pill">Presentation Demo · Local CSV</div>'
    '</div>'
)

html(
    '<section class="hero-card">'
    '<div class="hero-copy">'
    '<div class="hero-kicker">KAIST AI COLLEGE RAG GUIDE</div>'
    '<h1 class="hero-title">'
    'Explore <span class="blue-text">KAIST AI College</span><br>'
    'with a RAG Chatbot'
    '</h1>'
    '<p class="hero-desc">'
    '입학 정보, 학과·연구 분야, 교수진, 교과목 데이터를 '
    '질문 기반으로 탐색하는 발표용 RAG 챗봇 프론트엔드 데모입니다.'
    '</p>'
    '<div class="badge-row">'
    '<span class="badge">문서 기반 답변</span>'
    '<span class="badge">출처 카드 제공</span>'
    '<span class="badge">Streamlit Front-end</span>'
    '</div>'
    '</div>'
    '<div class="hero-image-wrap">'
    f'{kaist_img_tag}'
    '</div>'
    '</section>'
)

html('<div class="section-title">Start Here</div>')

col1, col2, col3 = st.columns(3)

with col1:
    html(
        '<div class="info-card start-card">'
        '<div class="icon-box">🏛️</div>'
        '<h3>AI College 소개</h3>'
        '<p>서비스 목적, 데이터 구성, RAG Guide의 사용자 흐름을 확인합니다.</p>'
        '</div>'
    )
    st.page_link(
        "pages/1_AI_College_Intro.py",
        label="AI College 소개 보기",
        use_container_width=True,
    )

with col2:
    html(
        '<div class="info-card start-card">'
        '<div class="icon-box">🔎</div>'
        '<h3>Departments</h3>'
        '<p>학과, 연구 분야, 교수진, 교과목 정보를 카드형 화면으로 탐색합니다.</p>'
        '</div>'
    )
    st.page_link(
        "pages/2_Departments.py",
        label="Departments 보기",
        use_container_width=True,
    )

with col3:
    html(
        '<div class="info-card start-card">'
        '<div class="icon-box">💬</div>'
        '<h3>RAG Chatbot</h3>'
        '<p>질문을 입력하고 답변과 참고 문서 카드가 함께 나오는 흐름을 시연합니다.</p>'
        '</div>'
    )
    st.page_link(
        "pages/3_RAG_Chatbot.py",
        label="챗봇 시작하기",
        use_container_width=True,
    )

html('<div class="section-title">What Users Can Do</div>')

u1, u2, u3 = st.columns(3)

with u1:
    html(
        '<div class="mini-card">'
        '<h3>입학 정보 탐색</h3>'
        '<p>지원 과정, 제출 서류, 모집 안내처럼 흩어진 정보를 질문으로 확인합니다.</p>'
        '</div>'
    )

with u2:
    html(
        '<div class="mini-card">'
        '<h3>연구 분야 비교</h3>'
        '<p>학과와 연구 키워드를 기준으로 관심 분야를 빠르게 살펴봅니다.</p>'
        '</div>'
    )

with u3:
    html(
        '<div class="mini-card">'
        '<h3>교수진·교과목 확인</h3>'
        '<p>교수진, 교과목, 행사 데이터를 챗봇 답변과 출처 카드로 연결합니다.</p>'
        '</div>'
    )