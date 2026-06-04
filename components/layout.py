import streamlit as st

KAIST_IMAGE_URL = "https://i.ibb.co/675rFvd7/326685445-5901197959968048-7858770690322114254-n.png"


def render_topbar():
    st.markdown(
        """
        <div class="topbar">
            <div class="brand">
                <div class="brand-mark">AI</div>
                <div>
                    <div class="brand-title">KAIST AI College<br>RAG Guide</div>
                    <div class="brand-subtitle">Document-grounded guide for prospective students</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero():
    st.markdown(
        f"""
        <section class="hero">
            <div class="hero-inner">
                <div>
                    <div class="hero-kicker">KAIST AI College RAG Guide</div>
                    <div class="hero-title">
                        Explore <span>KAIST AI College</span><br>
                        with a RAG Chatbot
                    </div>
                    <div class="hero-desc">
                        입학 정보, 학과·연구 분야, 교수진, 교과목 데이터를 질문 기반으로 탐색하는
                        발표용 RAG 챗봇 프론트엔드 데모입니다.
                    </div>
                    <div class="badge-row">
                        <div class="badge">문서 기반 답변</div>
                        <div class="badge">출처 카드 제공</div>
                        <div class="badge">Streamlit Front-end</div>
                    </div>
                </div>
                <div class="hero-image-box">
                    <img src="{KAIST_IMAGE_URL}" alt="KAIST campus image" />
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(kicker: str, title: str, description: str):
    st.markdown(
        f"""
        <section class="page-header">
            <div class="hero-kicker">{kicker}</div>
            <h1>{title}</h1>
            <p>{description}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_info_card(title: str, body: str):
    st.markdown(
        f"""
        <div class="info-card">
            <h3>{title}</h3>
            <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_source_cards(sources):
    if not sources:
        return

    # 출처 목록을 접을 수 있게 expander로 감싼다. 기본은 닫힌 상태라
    # 답변 영역이 뚱뚱해 보이지 않고, 필요할 때만 펼쳐서 확인할 수 있다.
    with st.expander("📎 Retrieved Sources", expanded=False):
        for source in sources:
            title = source.get("title", "Untitled Source")
            meta = source.get("meta", "Demo Source")
            url = source.get("url", "")
            title_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title
            st.markdown(
                f'<div class="source-card">'
                f'<div class="source-title">{title_html}</div>'
                f'<div class="source-meta">{meta}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_back_home():
    st.markdown('<div class="back-nav">', unsafe_allow_html=True)
    st.page_link("streamlit_app.py", label="← Home으로 돌아가기")
    st.markdown('</div>', unsafe_allow_html=True)
