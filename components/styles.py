import streamlit as st


def load_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

        /* ── Design Tokens ── */
        :root {
            --kaist-blue:   #005bac;
            --kaist-blue-2: #0077e6;
            --kaist-light:  #eef7ff;
            --ink:          #102033;
            --muted:        #5f7188;
            --line:         #d8e8f8;
            --card:         #ffffff;
        }

        /* ── Base ── */
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at 18%  8%, rgba(0, 91, 172, 0.08), transparent 28%),
                radial-gradient(circle at 88% 12%, rgba(0, 119, 230, 0.08), transparent 30%),
                linear-gradient(180deg, #ffffff 0%, #f8fbff 48%, #ffffff 100%);
            color: var(--ink);
        }

        .block-container {
            max-width: 1180px;
            padding-top: 1.2rem;
            padding-bottom: 3rem;
        }

        [data-testid="stHeader"] {
            height: 0;
            background: transparent;
        }

        [data-testid="stDecoration"],
        [data-testid="stToolbar"],
        [data-testid="stSidebar"],
        [data-testid="collapsedControl"] {
            display: none;
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--ink);
            letter-spacing: -0.035em;
        }

        p {
            color: var(--muted);
            line-height: 1.75;
        }

        a {
            text-decoration: none !important;
        }

        hr {
            border-color: var(--line);
        }

        /* ── Topbar ── */
        .topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.6rem;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }

        .brand-mark {
            width: 48px;
            height: 48px;
            border-radius: 14px;
            background: linear-gradient(135deg, var(--kaist-blue), var(--kaist-blue-2));
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            box-shadow: 0 12px 28px rgba(0, 91, 172, 0.22);
        }

        .brand-title {
            font-weight: 900;
            color: var(--ink);
            font-size: 1.02rem;
            line-height: 1.1;
        }

        .brand-subtitle {
            color: var(--muted);
            font-size: 0.82rem;
            margin-top: 0.18rem;
        }

        .demo-pill {
            display: none !important;
        }

        /* ── Landing / Hero card ── */
        .landing-card {
            display: grid;
            grid-template-columns: minmax(0, 1.12fr) minmax(320px, 0.88fr);
            gap: 2.2rem;
            align-items: center;
            padding: 2.7rem;
            border-radius: 28px;
            background: linear-gradient(135deg, #ffffff 0%, #eef7ff 100%);
            border: 1px solid var(--line);
            box-shadow: 0 24px 70px rgba(0, 91, 172, 0.12);
            margin-bottom: 2rem;
        }

        .landing-card .hero-image-wrap {
            margin-top: 1.35rem;
        }

        .hero-card {
            display: grid;
            grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
            gap: 2rem;
            align-items: center;
            padding: 2.7rem;
            border-radius: 28px;
            background: linear-gradient(135deg, #ffffff 0%, #eef7ff 100%);
            border: 1px solid var(--line);
            box-shadow: 0 24px 70px rgba(0, 91, 172, 0.12);
            margin-bottom: 2rem;
        }

        .hero-copy {
            min-width: 0;
        }

        .hero-kicker {
            color: var(--kaist-blue);
            font-weight: 900;
            font-size: 0.82rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 1rem;
        }

        .hero-title {
            font-size: 3.15rem;
            line-height: 1.05;
            font-weight: 900;
            color: var(--ink);
            margin-bottom: 1.15rem;
        }

        .blue-text {
            color: var(--kaist-blue);
        }

        .hero-desc {
            font-size: 1.02rem;
            color: var(--muted);
            line-height: 1.8;
            max-width: 620px;
            margin-bottom: 1.25rem;
        }

        /* ── Badges ── */
        .badge-row {
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
        }

        .badge {
            padding: 0.48rem 0.78rem;
            border-radius: 999px;
            background: white;
            color: var(--kaist-blue);
            border: 1px solid var(--line);
            font-size: 0.83rem;
            font-weight: 800;
        }

        /* ── Hero image ── */
        .hero-image-wrap {
            width: 100%;
            height: 260px;
            border-radius: 24px;
            background: #ffffff;
            border: 1px solid #dbeafe;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            box-shadow:
                inset 0 0 0 1px rgba(255, 255, 255, 0.7),
                0 18px 42px rgba(0, 91, 172, 0.08);
        }

        .hero-image-wrap img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            object-position: center;
            padding: 24px;
            display: block;
        }

        /* ── Feature panel ── */
        .feature-panel {
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 1.35rem;
            padding-left: 0.35rem;
        }

        .feature-panel-title {
            color: var(--ink);
            font-weight: 900;
            font-size: 1.55rem;
            letter-spacing: -0.04em;
            margin-bottom: 0.25rem;
        }

        .feature-item {
            display: grid;
            grid-template-columns: 38px 1fr;
            gap: 0.9rem;
            align-items: start;
        }

        .feature-icon {
            width: 38px;
            height: 38px;
            border-radius: 13px;
            background: rgba(255, 255, 255, 0.78);
            border: 1px solid rgba(216, 232, 248, 0.95);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.12rem;
        }

        .feature-item h3 {
            margin: 0 0 0.3rem 0;
            font-size: 1.35rem;
            line-height: 1.2;
            font-weight: 900;
            color: var(--ink);
        }

        .feature-item p {
            margin: 0;
            font-size: 0.94rem;
            line-height: 1.65;
            color: var(--muted);
        }

        /* ── Section title ── */
        .section-title {
            font-size: 1.35rem;
            font-weight: 900;
            color: var(--ink);
            margin: 2rem 0 1rem 0;
            letter-spacing: -0.04em;
        }

        /* ── Info / mini cards ── */
        .info-card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 1.35rem;
            box-shadow: 0 14px 34px rgba(0, 91, 172, 0.07);
            min-height: 150px;
        }

        .start-card {
            text-align: left;
            margin-bottom: 0.65rem;
        }

        .info-card h3 {
            margin: 0 0 0.7rem 0;
            color: var(--ink);
            font-size: 1.02rem;
            font-weight: 900;
        }

        .info-card p {
            margin: 0;
            color: var(--muted);
            font-size: 0.94rem;
        }

        .icon-box {
            width: 42px;
            height: 42px;
            border-radius: 14px;
            background: var(--kaist-light);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1rem;
            font-size: 1.2rem;
        }

        .mini-card {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 1.2rem;
            box-shadow: 0 10px 28px rgba(0, 91, 172, 0.06);
            min-height: 150px;
        }

        .mini-card h3 {
            margin: 0 0 0.6rem 0;
            font-size: 1rem;
            color: var(--ink);
        }

        .mini-card p {
            margin: 0;
            font-size: 0.92rem;
            color: var(--muted);
        }


        /* ── Department page: fixed 2x2 card height ── */
        .department-overview-card {
            height: 220px;
            min-height: 220px;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }

        .department-overview-card .department-icon {
            font-size: 2rem;
            line-height: 1;
            margin-bottom: 1.05rem;
        }

        .department-overview-card h3 {
            margin: 0 0 0.72rem 0;
        }

        .department-overview-card p {
            margin: 0;
            flex: 1;
        }

        .department-overview-card .card-link-wrap {
            margin-top: 0.75rem;
        }

        .department-overview-card .card-link {
            font-size: 0.8rem;
            font-weight: 800;
            color: var(--kaist-blue);
        }

        /* ── Department page: chair cards ── */
        .faculty-chair-card {
            height: 150px;
            min-height: 150px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding-bottom: 1.05rem;
        }

        .faculty-chair-card .faculty-dept-label {
            font-size: 0.75rem;
            color: var(--kaist-blue);
            font-weight: 800;
            margin-bottom: 0.65rem;
        }

        .faculty-chair-card h3 {
            margin: 0;
        }

        .faculty-chair-card p {
            margin: 0;
            font-size: 0.85rem;
            color: var(--muted);
        }



        /* ── Department page: compact course cards ── */
        .course-list-wrap {
            max-width: 820px;
        }

        .compact-course-card {
            min-height: 58px !important;
            padding: 0.82rem 1.2rem !important;
            display: flex;
            align-items: center;
            margin-bottom: 0.52rem !important;
        }

        .compact-course-card .course-line {
            display: flex;
            align-items: baseline;
            gap: 0.42rem;
            flex-wrap: wrap;
            line-height: 1.35;
        }

        .compact-course-card .course-title,
        .compact-course-card .course-title:visited {
            color: var(--kaist-blue) !important;
            font-size: 1.08rem !important;
            font-weight: 900 !important;
            letter-spacing: -0.035em;
        }

        .compact-course-card .course-title:hover {
            color: var(--kaist-blue-2) !important;
        }

        .compact-course-card .course-meta {
            color: var(--muted);
            font-size: 0.88rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .compact-course-card h3 {
            margin: 0 !important;
            font-size: 0.98rem !important;
            line-height: 1.35 !important;
            font-weight: 900;
        }

        .course-dept {
            color: var(--muted);
            font-weight: 700;
        }

        /* ── Page header ── */
        .page-header {
            padding: 2.2rem;
            border-radius: 28px;
            background: linear-gradient(135deg, #ffffff 0%, #eef7ff 100%);
            border: 1px solid var(--line);
            box-shadow: 0 18px 54px rgba(0, 91, 172, 0.1);
            margin-bottom: 1.6rem;
        }

        .page-header h1 {
            font-size: 2.4rem;
            font-weight: 900;
            color: var(--ink);
            margin: 0 0 0.6rem 0;
        }

        .page-header p {
            max-width: 760px;
            margin: 0;
            color: var(--muted);
            font-size: 1rem;
        }

        /* ── Source cards ── */
        .source-wrap {
            margin-top: 0.75rem;
            padding: 0.85rem;
            border-radius: 14px;
            background: #f7fbff;
            border: 1px solid var(--line);
        }

        .source-card {
            padding: 0.7rem 0.85rem;
            border-radius: 12px;
            background: #ffffff;
            border: 1px solid var(--line);
            margin-top: 0.45rem;
        }

        .source-title {
            color: var(--ink);
            font-weight: 800;
            font-size: 0.9rem;
        }

        .source-title a {
            color: var(--kaist-blue);
            font-weight: 900;
        }

        .source-meta {
            color: var(--muted);
            font-size: 0.78rem;
            margin-top: 0.2rem;
        }

        /* ── Metric ── */
        .stMetric {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 1rem;
            box-shadow: 0 10px 28px rgba(0, 91, 172, 0.06);
        }

        /* ════════════════════════════════════════
           Chat messages
           ════════════════════════════════════════ */

        /*
           목표
           - 메시지끼리는 촘촘하게 쌓이게 유지
           - 각 말풍선 안에서는 아바타와 텍스트가 세로 중앙에 오게 조정
           - 2~4줄 답변도 위/아래 여백이 균형 있게 보이도록 padding 확보
        */

        /* 1. 메시지 말풍선 기본 외형 */
        .stChatMessage {
            background: #ffffff !important;
            border: 1px solid var(--line) !important;
            border-radius: 16px !important;
            padding: 0.82rem 0.95rem !important;
            box-shadow: 0 4px 14px rgba(0, 91, 172, 0.06) !important;
            margin-top: 0 !important;
            margin-bottom: 0.45rem !important;
            min-height: 54px !important;

            display: flex !important;
            align-items: center !important;
        }

        /* 2. 스크롤 컨테이너(border=True) 내부 메시지도 동일하게 적용 */
        [data-testid="stVerticalBlockBorderWrapper"] .stChatMessage {
            padding: 0.82rem 0.95rem !important;
            margin-top: 0 !important;
            margin-bottom: 0.45rem !important;
            border-radius: 16px !important;
            min-height: 54px !important;

            display: flex !important;
            align-items: center !important;
        }

        /* 3. Streamlit 기본 vertical block gap 축소 */
        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] {
            gap: 0.42rem !important;
        }

        /* 4. 아바타 영역 중앙 정렬 */
        .stChatMessage [data-testid="stChatMessageAvatar"] {
            align-self: center !important;
            margin-top: 0 !important;
            margin-bottom: 0 !important;
            flex-shrink: 0 !important;
        }

        /* 5. 텍스트 컨텐츠 영역 중앙 정렬 */
        [data-testid="stChatMessageContent"] {
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            align-self: center !important;
            padding: 0.05rem 0 !important;
            gap: 0 !important;
            min-height: 38px !important;
        }

        [data-testid="stChatMessageContent"] > div {
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            min-height: 38px !important;
        }

        /* 6. Markdown 내부 여백 리셋: 3줄 이상에서도 아래 여백이 사라지지 않도록 조정 */
        .stChatMessage [data-testid="stMarkdownContainer"] {
            display: block !important;
            padding: 0 !important;
            margin: 0 !important;
        }

        .stChatMessage p {
            margin: 0 !important;
            padding: 0.05rem 0 !important;
            line-height: 1.58 !important;
            color: #111111 !important;
        }

        .stChatMessage p + p {
            margin-top: 0.35rem !important;
        }

        .stChatMessage ul,
        .stChatMessage ol {
            margin-top: 0.35rem !important;
            margin-bottom: 0.2rem !important;
            padding-left: 1.25rem !important;
        }

        .stChatMessage li {
            margin: 0.12rem 0 !important;
            line-height: 1.55 !important;
            color: #111111 !important;
        }

        /* 7. 버블 내부 텍스트 색상 */
        .stChatMessage span,
        .stChatMessage div,
        .stChatMessage table,
        .stChatMessage th,
        .stChatMessage td {
            color: #111111 !important;
        }

        /* 8. Expander / Warnings가 있을 때 말풍선 하단이 붙어 보이지 않도록 */
        .stChatMessage details {
            margin-top: 0.55rem !important;
            margin-bottom: 0.08rem !important;
        }

        /* ── Chat input ── */
        .stChatInput {
            background: #ffffff;
        }

        .stChatInput textarea {
            border-radius: 18px !important;
            border: 1px solid var(--line) !important;
        }

        /* ── Buttons ── */
        button[kind="secondary"] {
            border-radius: 14px !important;
            border: 1px solid var(--line) !important;
            background: #ffffff !important;
            color: var(--kaist-blue) !important;
            font-weight: 800 !important;
            transition: all 0.22s ease;
        }

        button[kind="secondary"]:hover {
            border-color: var(--kaist-blue) !important;
            background: #f0f8ff !important;
            transform: translateY(-1px);
        }

        /* ── Page links ── */
        div[data-testid="stPageLink"] {
            width: 100% !important;
        }

        .stPageLink a,
        div[data-testid="stPageLink"] a {
            width: 100% !important;
            min-height: 52px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
            background: linear-gradient(135deg, #005bac 0%, #0077e6 100%) !important;
            color: #ffffff !important;
            border-radius: 14px !important;
            border: none !important;
            padding: 0.75rem 1rem !important;
            font-weight: 800 !important;
            font-size: 0.95rem !important;
            box-shadow: 0 8px 20px rgba(0, 91, 172, 0.18);
            transition: all 0.25s ease;
        }

        .stPageLink a:hover,
        div[data-testid="stPageLink"] a:hover {
            background: linear-gradient(135deg, #004a91 0%, #006fd6 100%) !important;
            transform: translateY(-2px);
            box-shadow: 0 12px 28px rgba(0, 91, 172, 0.28);
            color: #ffffff !important;
        }

        .stPageLink a *,
        div[data-testid="stPageLink"] a * {
            color: #ffffff !important;
            opacity: 1 !important;
            text-align: center !important;
            justify-content: center !important;
        }

        .stPageLink a span,
        div[data-testid="stPageLink"] a span {
            width: 100% !important;
            text-align: center !important;
        }

        .stPageLink a svg,
        div[data-testid="stPageLink"] a svg {
            color: #ffffff !important;
            fill: #ffffff !important;
            stroke: #ffffff !important;
        }

        /* ── Responsive ── */
        @media (max-width: 900px) {
            .landing-card,
            .hero-card {
                grid-template-columns: 1fr;
                padding: 1.7rem;
            }

            .feature-panel {
                padding-left: 0;
            }

            .feature-item h3 {
                font-size: 1.2rem;
            }

            .hero-title {
                font-size: 2.15rem;
            }

            .topbar {
                flex-direction: column;
                align-items: flex-start;
                gap: 1rem;
            }

            .hero-image-wrap {
                height: 220px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
