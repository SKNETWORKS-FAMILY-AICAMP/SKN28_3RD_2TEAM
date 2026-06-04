from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_DIR = BASE_DIR / "processed" / "csv"

DEPT_LABELS = {
    "aic": "AI컴퓨팅학과",
    "ai_systems": "AI시스템학과",
    "ai_future": "AI미래학과",
    "ax": "AX학과",
    "fx": "AI미래학과",
}

DEPT_ORDER = ["AI컴퓨팅학과", "AI시스템학과", "AI미래학과", "AX학과"]


def load_csv(*filenames: str) -> pd.DataFrame:
    """
    data/processed/csv 하위 CSV를 읽습니다.
    파일명이 *_clean.csv 또는 기존 짧은 이름으로 섞여 있어도 동작하도록 fallback을 둡니다.
    """
    for filename in filenames:
        path = CSV_DIR / filename
        if path.exists():
            return pd.read_csv(path)
    return pd.DataFrame()


admissions_df = load_csv("admissions.csv", "admissions_clean.csv")
courses_df = load_csv("courses.csv", "courses_clean.csv")
people_df = load_csv("people.csv", "people_clean.csv")
events_df = load_csv("events.csv", "events_clean.csv")
assets_df = load_csv("assets.csv", "assets_clean.csv")
course_track_df = load_csv("course_track_map.csv")
department_offices_df = load_csv("department_offices.csv")
kaist_links_df = load_csv("kaist_links.csv")
kaist_profile_df = load_csv("kaist_profile.csv")
kaist_statistics_df = load_csv("kaist_statistics.csv")
rag_chunks_df = pd.DataFrame()
rag_documents_df = pd.DataFrame()


def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_url(value) -> str:
    url = safe_text(value)
    if url.startswith(("http://", "https://")):
        return url
    return ""


def get_data_summary():
    return {
        "admissions": len(admissions_df),
        "courses": len(courses_df),
        "course_tracks": len(course_track_df),
        "people": len(people_df),
        "events": len(events_df),
        "assets": len(assets_df),
        "rag_chunks": len(rag_chunks_df),
        "rag_documents": len(rag_documents_df),
    }


def get_department_heads():
    """
    지정한 4개 학과 학과장을 people.csv에서 이름으로 찾아 반환합니다.

    - 화면에는 직함을 모두 '학과장'으로 표시합니다.
    - 교수님 이름을 누르면 people.csv의 homepage 또는 source_url로 이동합니다.
    - dept_name 매칭이 실패해도 이름으로 한 번 더 찾아 fallback합니다.
    """
    if people_df.empty:
        return []

    chair_map = {
        "AI컴퓨팅학과": "이의진",
        "AI시스템학과": "제민규",
        "AI미래학과": "김형준",
        "AX학과": "유승화",
    }

    rows = people_df.copy().fillna("")
    result = []

    def contains_in_column(df: pd.DataFrame, column: str, keyword: str) -> pd.Series:
        if column not in df.columns:
            return pd.Series(False, index=df.index)
        return df[column].astype(str).str.contains(keyword, na=False, regex=False)

    def equals_in_column(df: pd.DataFrame, column: str, value: str) -> pd.Series:
        if column not in df.columns:
            return pd.Series(False, index=df.index)
        return df[column].astype(str).eq(value)

    for dept_name, chair_name in chair_map.items():
        name_mask = (
            contains_in_column(rows, "name_ko", chair_name)
            | contains_in_column(rows, "name", chair_name)
        )
        dept_mask = equals_in_column(rows, "dept_name", dept_name)

        matched = rows[name_mask & dept_mask]
        if matched.empty:
            matched = rows[name_mask]

        if matched.empty:
            result.append(
                {
                    "dept_name": dept_name,
                    "name_ko": chair_name,
                    "role_normalized": "학과장",
                    "homepage": "",
                }
            )
            continue

        item = matched.iloc[0].to_dict()
        item["dept_name"] = dept_name
        item["name_ko"] = chair_name
        item["role_normalized"] = "학과장"
        item["homepage"] = (
            _normalize_url(item.get("homepage"))
            or _normalize_url(item.get("source_url"))
            or _normalize_url(item.get("url"))
        )
        result.append(item)

    return result


def get_departments():
    return [
        {
            "dept_name": "AI컴퓨팅학과",
            "summary": "AI 알고리즘, 머신러닝, 컴퓨팅 기반 기술, 데이터 처리 역량 중심 학과입니다.",
            "source_url": "https://aic.kaist.ac.kr",
        },
        {
            "dept_name": "AI시스템학과",
            "summary": "지능형 소프트웨어, AI 플랫폼, 응용 시스템 설계를 중심으로 한 학과입니다.",
            "source_url": "https://ais.kaist.ac.kr",
        },
        {
            "dept_name": "AI미래학과",
            "summary": "미래 사회 문제와 AI 융합 연구를 연결하는 학제간 융합 학과입니다.",
            "source_url": "https://aif.kaist.ac.kr",
        },
        {
            "dept_name": "AX학과",
            "summary": "AI 전환(AI Transformation)과 산업·사회 적용을 중심으로 한 융합 학과입니다.",
            "source_url": "https://ax.kaist.ac.kr",
        },
    ]


def _sample_by_dept(df: pd.DataFrame, cols: list, limit: int) -> list:
    """학과별 균등 샘플링."""
    available_cols = [c for c in cols if c in df.columns]
    if not available_cols:
        return []

    sub = df[available_cols].fillna("")

    if "dept_name" in df.columns:
        depts = [dept for dept in DEPT_ORDER if dept in set(df["dept_name"].fillna(""))]
        per_dept = max(1, limit // max(1, len(depts)))
        frames = [sub[df["dept_name"] == dept].head(per_dept) for dept in depts]
        if frames:
            return pd.concat(frames).head(limit).to_dict("records")

    if "dept" in df.columns:
        depts = df["dept"].dropna().unique()
        per_dept = max(1, limit // max(1, len(depts)))
        frames = [sub[df["dept"] == dept].head(per_dept) for dept in depts]
        if frames:
            return pd.concat(frames).head(limit).to_dict("records")

    return sub.head(limit).to_dict("records")


def get_representative_people(limit=9):
    if people_df.empty:
        return []
    cols = ["dept_name", "name", "name_ko", "role", "research_area", "homepage", "source_url"]
    return _sample_by_dept(people_df, cols, limit)


def _build_course_track_df() -> pd.DataFrame:
    """
    Representative Courses 화면용 데이터셋을 만듭니다.

    1순위: course_track_map.csv
    2순위: courses.csv
    """
    if not course_track_df.empty:
        preferred_cols = [
            "dept_name",
            "dept",
            "course_code",
            "course_name",
            "track_name",
            "course_type",
            "source_url",
        ]
        available_cols = [col for col in preferred_cols if col in course_track_df.columns]
        df = course_track_df[available_cols].copy().fillna("")
    elif not courses_df.empty:
        preferred_cols = [
            "dept_name",
            "dept",
            "course_code",
            "course_name",
            "course_type",
            "source_url",
        ]
        available_cols = [col for col in preferred_cols if col in courses_df.columns]
        df = courses_df[available_cols].copy().fillna("")
        if "track_name" not in df.columns:
            df["track_name"] = ""
    else:
        return pd.DataFrame()

    if "dept_name" not in df.columns and "dept" in df.columns:
        df["dept_name"] = df["dept"].map(DEPT_LABELS).fillna(df["dept"].astype(str))

    for col in ["dept_name", "course_code", "course_name", "track_name", "course_type", "source_url"]:
        if col not in df.columns:
            df[col] = ""

    df["course_code"] = df["course_code"].astype(str).str.strip()
    df["course_name"] = df["course_name"].astype(str).str.strip()
    df["dept_name"] = df["dept_name"].astype(str).str.strip()
    df["track_name"] = df["track_name"].astype(str).str.strip()
    df["course_type"] = df["course_type"].astype(str).str.strip()

    df = df[(df["course_code"] != "") | (df["course_name"] != "")]
    df = df.drop_duplicates(subset=["dept_name", "course_code", "course_name", "track_name", "course_type"])
    return df


def get_representative_courses(limit=8):
    """학과별 대표 과목을 2개씩 균등하게 반환합니다."""
    df = _build_course_track_df()
    if df.empty:
        return []

    result = []
    per_dept = max(1, limit // len(DEPT_ORDER))

    for dept_name in DEPT_ORDER:
        dept_rows = df[df["dept_name"] == dept_name].copy()
        if dept_rows.empty:
            continue

        result.extend(dept_rows.head(per_dept).to_dict("records"))

    if len(result) < limit:
        used_keys = {
            (
                item.get("dept_name", ""),
                item.get("course_code", ""),
                item.get("course_name", ""),
                item.get("track_name", ""),
            )
            for item in result
        }
        for item in df.to_dict("records"):
            key = (
                item.get("dept_name", ""),
                item.get("course_code", ""),
                item.get("course_name", ""),
                item.get("track_name", ""),
            )
            if key in used_keys:
                continue
            result.append(item)
            used_keys.add(key)
            if len(result) >= limit:
                break

    return result[:limit]


def search_chunks(query: str, limit=3):
    if rag_chunks_df.empty:
        return []

    q = query.lower()
    keywords = [word for word in q.replace("?", " ").replace(",", " ").split() if len(word) >= 2]
    if not keywords:
        return []

    scored = []
    for _, row in rag_chunks_df.iterrows():
        text = safe_text(row.get("chunk_text", row.get("text", "")))
        title = safe_text(row.get("title", row.get("document_title", "")))
        dept_name = safe_text(row.get("dept_name", row.get("dept", "")))
        source_url = safe_text(row.get("source_url", ""))
        combined = f"{title} {text}".lower()
        score = sum(1 for keyword in keywords if keyword in combined)
        if score > 0:
            scored.append(
                {
                    "score": score,
                    "title": title,
                    "dept_name": dept_name,
                    "text": text,
                    "source_url": source_url,
                }
            )

    return sorted(scored, key=lambda x: x["score"], reverse=True)[:limit]


def _rows_to_sources(rows, fallback_title="Document", meta="Local CSV"):
    sources = []
    for _, row in rows.iterrows():
        title = safe_text(row.get("title", row.get("course_name", row.get("name", fallback_title))))
        dept_name = safe_text(row.get("dept_name", row.get("dept", "")))
        url = _normalize_url(row.get("source_url")) or _normalize_url(row.get("homepage"))
        sources.append(
            {
                "title": title or fallback_title,
                "meta": f"{dept_name} · {meta}" if dept_name else meta,
                "url": url,
            }
        )
    return sources[:3]


def get_admission_answer():
    if admissions_df.empty:
        return {
            "answer": "입학 데이터가 아직 준비되지 않았습니다. data/processed/csv/admissions.csv 파일을 추가하면 이 영역이 자동으로 채워집니다.",
            "sources": [],
        }

    rows = admissions_df.fillna("").head(5)
    lines = []
    for _, row in rows.iterrows():
        dept_name = safe_text(row.get("dept_name", ""))
        title = safe_text(row.get("title", row.get("section_title", "Admission")))
        content = safe_text(row.get("content", row.get("text", "")))
        lines.append(f"- {dept_name}: {title} — {content[:160]}")

    return {
        "answer": "KAIST AI College 입학 정보에서 확인할 수 있는 주요 항목입니다.\n\n" + "\n".join(lines),
        "sources": _rows_to_sources(rows, "Admission", "Admission"),
    }


def get_research_answer():
    chunks = search_chunks("연구 분야 research lab faculty", limit=3)
    if not chunks:
        return {
            "answer": "KAIST AI College는 Machine Learning, Deep Learning, NLP, Computer Vision, Robotics, Human-Centered AI, Trustworthy AI 등 다양한 AI 연구 분야를 탐색할 수 있도록 구성됩니다.",
            "sources": [],
        }

    lines = [f"- {item['dept_name']}: {item['text'][:220]}" for item in chunks]
    sources = [
        {
            "title": item["title"] or "Research Information",
            "meta": f"{item['dept_name']} · RAG Chunk",
            "url": _normalize_url(item["source_url"]),
        }
        for item in chunks
    ]

    return {
        "answer": "관련 문서에서 검색된 연구 분야 정보입니다.\n\n" + "\n".join(lines),
        "sources": sources,
    }


def get_faculty_answer():
    if people_df.empty:
        return {
            "answer": "교수진 데이터가 아직 준비되지 않았습니다. data/processed/csv/people.csv 파일을 추가하면 이 영역이 자동으로 채워집니다.",
            "sources": [],
        }

    rows = people_df.fillna("").head(6)
    lines = []
    for _, row in rows.iterrows():
        name = safe_text(row.get("name", ""))
        dept_name = safe_text(row.get("dept_name", ""))
        role = safe_text(row.get("role", ""))
        research_area = safe_text(row.get("research_area", ""))
        lines.append(f"- {name} / {dept_name}: {research_area or role}")

    return {
        "answer": "교수진 탐색은 연구 키워드와 학과 적합성을 중심으로 볼 수 있습니다.\n\n" + "\n".join(lines),
        "sources": _rows_to_sources(rows, "Faculty", "Faculty"),
    }


def get_course_answer():
    df = _build_course_track_df()
    if df.empty:
        return {
            "answer": "교과목 데이터가 아직 준비되지 않았습니다. data/processed/csv/course_track_map.csv 또는 courses.csv 파일을 추가하면 이 영역이 자동으로 채워집니다.",
            "sources": [],
        }

    rows = df.fillna("").head(6)
    lines = []
    for _, row in rows.iterrows():
        dept_name = safe_text(row.get("dept_name", ""))
        code = safe_text(row.get("course_code", ""))
        name = safe_text(row.get("course_name", ""))
        track = safe_text(row.get("track_name", ""))
        course_type = safe_text(row.get("course_type", ""))
        parts = [part for part in [dept_name, track, course_type] if part]
        lines.append(f"- {name} ({code}) · {' · '.join(parts)}")

    return {
        "answer": "데모 데이터에서 확인되는 교과목 예시는 다음과 같습니다.\n\n" + "\n".join(lines),
        "sources": _rows_to_sources(rows, "Course", "Course"),
    }


def get_event_answer():
    if events_df.empty:
        return {
            "answer": "행사 및 공지 데이터가 아직 준비되지 않았습니다. data/processed/csv/events.csv 파일을 추가하면 이 영역이 자동으로 채워집니다.",
            "sources": [],
        }

    rows = events_df.fillna("").head(4)
    lines = []
    for _, row in rows.iterrows():
        dept_name = safe_text(row.get("dept_name", ""))
        title = safe_text(row.get("title", ""))
        date = safe_text(row.get("event_date", row.get("date", "")))
        lines.append(f"- {dept_name}: {title} ({date})")

    return {
        "answer": "설명회나 공지성 정보는 다음과 같이 확인할 수 있습니다.\n\n" + "\n".join(lines),
        "sources": _rows_to_sources(rows, "Event", "Event"),
    }


def get_default_answer(question: str):
    chunks = search_chunks(question, limit=3)
    if chunks:
        lines = [f"- {item['dept_name']}: {item['text'][:220]}" for item in chunks]
        sources = [
            {
                "title": item["title"] or "Retrieved Document",
                "meta": f"{item['dept_name']} · RAG Chunk",
                "url": _normalize_url(item["source_url"]),
            }
            for item in chunks
        ]
        return {
            "answer": "질문과 관련된 문서 조각을 검색했습니다.\n\n" + "\n".join(lines),
            "sources": sources,
        }

    return {
        "answer": "입학, 연구 분야, 교수진, 교과목, 행사 정보를 중심으로 질문해보세요. 예: ‘입학 서류가 궁금해요’, ‘연구 분야 알려줘’, ‘교수진 정보 알려줘’. ",
        "sources": [{"title": "KAIST AI College Demo Knowledge Base", "meta": "Demo · Local CSV Data", "url": ""}],
    }


def get_demo_response(question: str):
    q = question.lower()
    if any(k in q for k in ["입학", "지원", "서류", "모집", "영어", "admission", "apply"]):
        return get_admission_answer()
    if any(k in q for k in ["연구", "분야", "랩", "연구실", "research", "lab"]):
        return get_research_answer()
    if any(k in q for k in ["교수", "교수진", "지도교수", "faculty", "professor"]):
        return get_faculty_answer()
    if any(k in q for k in ["교과", "수업", "과목", "course", "curriculum"]):
        return get_course_answer()
    if any(k in q for k in ["행사", "설명회", "이벤트", "공지", "event", "notice"]):
        return get_event_answer()
    return get_default_answer(question)
