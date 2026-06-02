# ============================================================
# KAIST 대학원 RAG Agent용 전처리 코드
# - SQL 적재용 CSV 생성
# - VectorStore 적재용 JSON / JSONL 생성
# - PDF 본문 추출
# - PDF 실패 시 attachments.text_preview fallback
# - vector 문서 품질 리포트 생성
# ============================================================

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# 0. 경로 설정
# ============================================================

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw_data"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SQL_DIR = PROCESSED_DIR / "csv"
VECTOR_DIR = PROCESSED_DIR / "json"
REPORT_DIR = PROCESSED_DIR / "reports"

for directory in [SQL_DIR, VECTOR_DIR, REPORT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


CSV_FILES = {
    "admissions": "admissions_clean.csv",
    "assets": "assets_clean.csv",
    "attachments": "attachments_clean.csv",
    "course_track_map": "course_track_map.csv",
    "courses": "courses_clean.csv",
    "events": "events_clean.csv",
    "people": "people_clean.csv",
    "quality_report": "quality_report.csv",
    "kaist_basic_info": "손지은_KAIST_공식홈페이지_조사 - 기본정보.csv",
    "department_offices": "손지은_KAIST_공식홈페이지_조사 - 학과사무실.csv",
}


PDF_FILES = {
    "AI_Computing_Grad_Info_Session_20260320(1).pdf": {
        "dept": "aic",
        "dept_name": "AI컴퓨팅학과",
        "document_type": "grad_info_session",
        "source_url": "https://aic.kaist.ac.kr/files/AI_Computing_Grad_Info_Session_20260320.pdf",
        "year": 2026,
        "semester": "fall",
    },
    "AI_Systems_Grad_Info_20260319(1).pdf": {
        "dept": "ai_systems",
        "dept_name": "AI시스템학과",
        "document_type": "grad_info_session",
        "source_url": "https://ai-systems.kaist.ac.kr/attachments/AI_Systems_Grad_Info_20260319.pdf",
        "year": 2026,
        "semester": "fall",
    },
    "KAIST AI & FUTURES STUDIES(1).pdf": {
        "dept": "fx",
        "dept_name": "AI미래학과",
        "document_type": "department_web_pdf",
        "source_url": "https://fx.kaist.ac.kr/#about",
        "year": 2026,
        "semester": "fall",
    },
    "KAIST AX (AI Transformation)(1).pdf": {
        "dept": "ax",
        "dept_name": "AX학과",
        "document_type": "department_web_pdf",
        "source_url": "https://ax.kaist.ac.kr/#/admission-grad",
        "year": 2026,
        "semester": "fall",
    },
}


# ============================================================
# 1. 공통 유틸 함수
# ============================================================

NULL_LIKE = {"", "nan", "none", "null", "na", "n/a", "-", "—"}


def is_empty(value: Any) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    text = str(value).strip()
    return text.lower() in NULL_LIKE


def clean_scalar(value: Any) -> str | None:
    if is_empty(value):
        return None

    text = str(value)
    text = text.replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if text.lower() in NULL_LIKE:
        return None

    return text


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df.columns = [
        clean_scalar(col) if clean_scalar(col) else f"unnamed_{idx}"
        for idx, col in enumerate(df.columns)
    ]

    for col in df.columns:
        df[col] = df[col].map(clean_scalar)

    df = df.dropna(how="all").reset_index(drop=True)
    return df


def read_csv_clean(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    return clean_dataframe(df)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def make_hash(*parts: Any, length: int = 16) -> str:
    raw = "||".join("" if part is None else str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def row_value(row: pd.Series, col: str) -> str | None:
    if col not in row:
        return None

    value = row[col]
    return None if is_empty(value) else str(value).strip()


def recompute_missing_fields(
    df: pd.DataFrame,
    exclude: tuple[str, ...] = ("missing_fields",),
) -> pd.DataFrame:
    df = df.copy()
    target_cols = [col for col in df.columns if col not in exclude]

    missing_values = []

    for _, row in df.iterrows():
        missing = [col for col in target_cols if is_empty(row.get(col))]
        missing_values.append(", ".join(missing) if missing else None)

    df["missing_fields"] = missing_values
    return df


def normalize_email(value: Any) -> str | None:
    if is_empty(value):
        return None

    text = str(value).strip()
    text = text.replace("mailto:", "").replace("MAILTO:", "").strip()

    match = re.search(
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
        text,
    )
    return match.group(0) if match else text


def normalize_course_code(value: Any) -> str | None:
    if is_empty(value):
        return None

    text = str(value).strip()
    text = re.sub(r"[^A-Za-z0-9가-힣]", "", text)
    return text.upper() if text else None


def normalize_date_yyyy_mm_dd(value: Any) -> str | None:
    if is_empty(value):
        return None

    text = str(value).strip()

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text

    match = re.search(
        r"(20\d{2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})",
        text,
    )

    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    return None


def extract_min_gpa(*values: Any) -> str | None:
    joined = " ".join(str(value) for value in values if not is_empty(value))

    patterns = [
        r"평점평균.{0,20}?(\d\.\d)",
        r"누적\s*평점.{0,20}?(\d\.\d)",
        r"GPA.{0,20}?(\d\.\d)",
        r"(\d\.\d)\s*이상",
    ]

    for pattern in patterns:
        match = re.search(pattern, joined, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def make_vector_doc(
    text: str,
    metadata: dict[str, Any],
    doc_id_seed: Any = None,
) -> dict[str, Any] | None:
    text = clean_scalar(text)

    if not text:
        return None

    cleaned_metadata = {
        key: (None if is_empty(value) else value)
        for key, value in metadata.items()
    }

    doc_id = make_hash(
        doc_id_seed or cleaned_metadata.get("source_type"),
        cleaned_metadata.get("dept"),
        cleaned_metadata.get("title"),
        cleaned_metadata.get("page"),
        text[:300],
        length=20,
    )

    return {
        "id": doc_id,
        "text": text,
        "metadata": cleaned_metadata,
    }


def add_doc(
    docs: list[dict[str, Any]],
    text: str,
    metadata: dict[str, Any],
    doc_id_seed: Any = None,
) -> None:
    doc = make_vector_doc(text, metadata, doc_id_seed=doc_id_seed)

    if doc:
        docs.append(doc)


def chunk_text_by_paragraphs(
    text: str,
    max_chars: int = 1200,
    overlap_chars: int = 120,
) -> list[str]:
    text = clean_scalar(text)

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        candidate = current + "\n\n" + paragraph if current else paragraph

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current.strip())

        if len(paragraph) > max_chars:
            start = 0

            while start < len(paragraph):
                end = start + max_chars
                chunks.append(paragraph[start:end].strip())

                next_start = end - overlap_chars
                if next_start <= start:
                    next_start = end

                start = next_start
        else:
            overlap = current[-overlap_chars:] if current else ""
            current = (overlap + "\n\n" + paragraph).strip() if overlap else paragraph

    if current:
        chunks.append(current.strip())

    return chunks


def safe_get_df(dfs: dict[str, pd.DataFrame], key: str) -> pd.DataFrame:
    if key not in dfs:
        return pd.DataFrame()

    return dfs[key].copy()


# ============================================================
# 2. CSV 로드
# ============================================================

dfs: dict[str, pd.DataFrame] = {}

for key, filename in CSV_FILES.items():
    path = RAW_DATA_DIR / filename
    dfs[key] = read_csv_clean(path)
    print(f"[로드 완료] {key}: {dfs[key].shape} - {filename}")


# ============================================================
# 3. SQL 적재용 CSV 생성
# ============================================================

# ------------------------------------------------------------
# 3-1. admissions
# ------------------------------------------------------------

admissions = safe_get_df(dfs, "admissions")

type_map = {
    "admission_eligibility": "eligibility",
    "admission_schedule": "schedule",
    "admission_schedule_or_process": "schedule",
    "scholarship": "scholarship",
    "advisor_matching": "advisor_matching",
    "admission_info": "general_info",
}

if "admission_type" in admissions.columns:
    admissions["admission_type_norm"] = admissions["admission_type"].map(
        lambda value: type_map.get(value, value)
    )
else:
    admissions["admission_type_norm"] = None

if "schedule_date" in admissions.columns:
    admissions["schedule_date_raw"] = admissions["schedule_date"]
else:
    admissions["schedule_date_raw"] = None
    admissions["schedule_date"] = None

admissions["schedule_date"] = admissions["schedule_date_raw"].map(
    normalize_date_yyyy_mm_dd
)

admissions["min_gpa"] = admissions.apply(
    lambda row: extract_min_gpa(
        row.get("schedule_date_raw"),
        row.get("title"),
        row.get("content"),
    ),
    axis=1,
)

admissions["admission_id"] = admissions.apply(
    lambda row: row.get("record_id") or make_hash(
        row.get("dept"),
        row.get("admission_type"),
        row.get("title"),
        row.get("content"),
    ),
    axis=1,
)

admissions = recompute_missing_fields(admissions)
save_csv(admissions, SQL_DIR / "admissions.csv")


# ------------------------------------------------------------
# 3-2. courses
# ------------------------------------------------------------

courses = safe_get_df(dfs, "courses")

if "course_code" in courses.columns:
    courses["course_code_norm"] = courses["course_code"].map(normalize_course_code)
else:
    courses["course_code_norm"] = None

courses["course_id"] = courses.apply(
    lambda row: row.get("record_id") or make_hash(
        row.get("dept"),
        row.get("course_code_norm"),
        row.get("course_name"),
    ),
    axis=1,
)

course_dedup_cols = [
    col
    for col in ["dept", "course_code_norm", "course_name", "course_type"]
    if col in courses.columns
]

if course_dedup_cols:
    courses = courses.drop_duplicates(
        subset=course_dedup_cols,
        keep="first",
    ).reset_index(drop=True)

courses = recompute_missing_fields(courses)
save_csv(courses, SQL_DIR / "courses.csv")


# ------------------------------------------------------------
# 3-3. course_track_map
# ------------------------------------------------------------

course_track_map = safe_get_df(dfs, "course_track_map")

if "course_code" in course_track_map.columns:
    course_track_map["course_code_norm"] = course_track_map["course_code"].map(
        normalize_course_code
    )
else:
    course_track_map["course_code_norm"] = None

course_track_map["course_track_id"] = course_track_map.apply(
    lambda row: make_hash(
        row.get("dept"),
        row.get("course_code_norm"),
        row.get("course_name"),
        row.get("track_name"),
    ),
    axis=1,
)

track_dedup_cols = [
    col
    for col in ["dept", "course_code_norm", "course_name", "track_name"]
    if col in course_track_map.columns
]

if track_dedup_cols:
    course_track_map = course_track_map.drop_duplicates(
        subset=track_dedup_cols,
        keep="first",
    ).reset_index(drop=True)

course_track_map = recompute_missing_fields(course_track_map)
save_csv(course_track_map, SQL_DIR / "course_track_map.csv")


# ------------------------------------------------------------
# 3-4. people
# ------------------------------------------------------------

people = safe_get_df(dfs, "people")

if "email" in people.columns:
    people["email"] = people["email"].map(normalize_email)
else:
    people["email"] = None

if "role_normalized" not in people.columns:
    people["role_normalized"] = None

people["role_normalized"] = people.apply(
    lambda row: row.get("role_normalized") or row.get("role"),
    axis=1,
)

people["person_id"] = people.apply(
    lambda row: row.get("record_id") or make_hash(
        row.get("dept"),
        row.get("name"),
        row.get("email"),
        row.get("homepage"),
    ),
    axis=1,
)

people_dedup_cols = [
    col
    for col in ["dept", "name", "email", "homepage"]
    if col in people.columns
]

if people_dedup_cols:
    people = people.drop_duplicates(
        subset=people_dedup_cols,
        keep="first",
    ).reset_index(drop=True)

people = recompute_missing_fields(people)
save_csv(people, SQL_DIR / "people.csv")


# ------------------------------------------------------------
# 3-5. events
# ------------------------------------------------------------

events = safe_get_df(dfs, "events")

if "event_date" in events.columns:
    events["event_date"] = events["event_date"].map(normalize_date_yyyy_mm_dd)
else:
    events["event_date"] = None

events["event_id"] = events.apply(
    lambda row: row.get("record_id") or make_hash(
        row.get("dept"),
        row.get("title"),
        row.get("event_date"),
    ),
    axis=1,
)

events = recompute_missing_fields(events)
save_csv(events, SQL_DIR / "events.csv")


# ------------------------------------------------------------
# 3-6. assets
# ------------------------------------------------------------

assets = safe_get_df(dfs, "assets")

assets["asset_id"] = assets.apply(
    lambda row: make_hash(
        row.get("dept"),
        row.get("source_url"),
        row.get("url"),
        row.get("content_type"),
        row.get("text"),
    ),
    axis=1,
)

VECTOR_ASSET_TYPES = {
    "contact_info",
    "link",
    "text",
    "table",
    "card",
    "mixed_media",
    "attachment",
}

assets["is_vector_candidate"] = assets.apply(
    lambda row: (
        row.get("content_type") in VECTOR_ASSET_TYPES
        and not is_empty(row.get("text"))
        and row.get("content_type") != "image"
    ),
    axis=1,
)

assets = recompute_missing_fields(assets)
save_csv(assets, SQL_DIR / "assets.csv")


# ------------------------------------------------------------
# 3-7. attachments
# ------------------------------------------------------------

attachments = safe_get_df(dfs, "attachments")

attachments["attachment_id"] = attachments.apply(
    lambda row: make_hash(
        row.get("dept"),
        row.get("filename"),
        row.get("url"),
    ),
    axis=1,
)

attachments["use_text_preview_for_vectorstore"] = False
attachments["note"] = "PDF 원문은 업로드된 PDF 파일에서 직접 추출. text_preview는 부분 미리보기라 vectorstore 제외."

attachments = recompute_missing_fields(attachments)
save_csv(attachments, SQL_DIR / "attachments.csv")


# ------------------------------------------------------------
# 3-8. quality_report
# ------------------------------------------------------------

quality_report = safe_get_df(dfs, "quality_report")
save_csv(quality_report, SQL_DIR / "quality_report.csv")


# ------------------------------------------------------------
# 3-9. KAIST 기본정보
# ------------------------------------------------------------

basic = safe_get_df(dfs, "kaist_basic_info")
basic = basic.dropna(how="all").reset_index(drop=True)

kaist_home_url = None

if "항목" in basic.columns and "내용" in basic.columns:
    url_rows = basic[basic["항목"] == "URL"]

    if len(url_rows) > 0:
        kaist_home_url = url_rows.iloc[0]["내용"]


kaist_links = pd.DataFrame(columns=["link_name", "url", "note", "source"])

if "내용" in basic.columns:
    kaist_links = basic[
        basic["내용"].fillna("").str.contains(r"https?://", regex=True)
    ].copy()

    kaist_links = kaist_links.rename(
        columns={
            "항목": "link_name",
            "내용": "url",
            "기타": "note",
        }
    )

    for col in ["link_name", "url", "note"]:
        if col not in kaist_links.columns:
            kaist_links[col] = None

    kaist_links["source"] = "KAIST 공식홈페이지 조사"
    kaist_links = kaist_links[["link_name", "url", "note", "source"]]

save_csv(kaist_links, SQL_DIR / "kaist_links.csv")


stat_rows: list[dict[str, Any]] = []
current_group = None
stat_group_names = {"졸업생", "재학생", "교직원"}

if len(basic) > 0:
    for _, row in basic.iterrows():
        item = row.get("항목")
        content = row.get("내용")
        note = row.get("기타")

        if item in stat_group_names:
            current_group = item
            continue

        if current_group and not is_empty(item):
            value_raw = content
            value_number = None

            if not is_empty(value_raw):
                match = re.search(r"[\d,]+", str(value_raw))
                if match:
                    value_number = match.group(0).replace(",", "")

            stat_rows.append({
                "stat_group": current_group,
                "level": item,
                "value_raw": value_raw,
                "value_number": value_number,
                "note": note,
                "source": "KAIST 공식홈페이지 조사",
            })

kaist_statistics = pd.DataFrame(
    stat_rows,
    columns=["stat_group", "level", "value_raw", "value_number", "note", "source"],
)
save_csv(kaist_statistics, SQL_DIR / "kaist_statistics.csv")


profile_rows: list[dict[str, Any]] = []

if len(basic) > 0:
    for _, row in basic.iterrows():
        item = row.get("항목")
        content = row.get("내용")
        note = row.get("기타")

        if is_empty(item) and is_empty(content):
            continue

        profile_rows.append({
            "item": item,
            "content": content,
            "note": note,
            "source_url": kaist_home_url,
            "source": "KAIST 공식홈페이지 조사",
        })

kaist_profile = pd.DataFrame(
    profile_rows,
    columns=["item", "content", "note", "source_url", "source"],
)
save_csv(kaist_profile, SQL_DIR / "kaist_profile.csv")


# ------------------------------------------------------------
# 3-10. department_offices
# ------------------------------------------------------------

department_offices = safe_get_df(dfs, "department_offices")

department_offices["office_id"] = department_offices.apply(
    lambda row: make_hash(
        row.get("program_name"),
        row.get("phone"),
        row.get("website"),
        row.get("building_location"),
    ),
    axis=1,
)

department_offices["source"] = department_offices.get(
    "source",
    "KAIST 공식홈페이지 조사",
)

department_offices["source_page"] = department_offices.get(
    "source_page",
    kaist_home_url,
)

department_offices = recompute_missing_fields(department_offices)
save_csv(department_offices, SQL_DIR / "department_offices.csv")


# ============================================================
# 4. VectorStore용 JSON 문서 생성
# ============================================================

vector_docs: list[dict[str, Any]] = []


# ------------------------------------------------------------
# 4-1. admissions -> vector docs
# ------------------------------------------------------------

for _, row in admissions.iterrows():
    title = row_value(row, "title") or row_value(row, "section_title") or "입학 정보"

    lines = [
        f"[{row_value(row, 'dept_name')} 입학 정보]",
        f"항목: {row_value(row, 'admission_type_norm') or row_value(row, 'admission_type')}",
        f"페이지 제목: {row_value(row, 'page_title')}",
        f"섹션: {row_value(row, 'section_title')}",
        f"제목: {title}",
        f"내용: {row_value(row, 'content')}",
    ]

    if row_value(row, "schedule_date"):
        lines.append(f"일정 기준일: {row_value(row, 'schedule_date')}")

    if row_value(row, "min_gpa"):
        lines.append(f"최소 평점 조건: {row_value(row, 'min_gpa')}")

    if row_value(row, "source_url"):
        lines.append(f"출처: {row_value(row, 'source_url')}")

    text = "\n".join([line for line in lines if not line.endswith("None")])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_admission",
            "content_type": "admission",
            "dept": row_value(row, "dept"),
            "dept_name": row_value(row, "dept_name"),
            "title": title,
            "section": row_value(row, "section_title"),
            "admission_type": row_value(row, "admission_type_norm"),
            "schedule_date": row_value(row, "schedule_date"),
            "source_url": row_value(row, "source_url"),
            "crawled_at": row_value(row, "crawled_at"),
        },
        doc_id_seed=row_value(row, "admission_id"),
    )


# ------------------------------------------------------------
# 4-2. courses + course_track_map -> vector docs
# ------------------------------------------------------------

if len(course_track_map) > 0 and {"dept", "course_code_norm"}.issubset(course_track_map.columns):
    track_group = (
        course_track_map
        .groupby(["dept", "course_code_norm"], dropna=False)
        .agg({
            "track_name": lambda x: sorted(set(v for v in x if not is_empty(v))),
            "course_description": lambda x: next((v for v in x if not is_empty(v)), None),
        })
        .reset_index()
    )
else:
    track_group = pd.DataFrame(
        columns=["dept", "course_code_norm", "track_name", "course_description"]
    )

courses_for_vector = courses.merge(
    track_group,
    on=["dept", "course_code_norm"],
    how="left",
    suffixes=("", "_track"),
)

for _, row in courses_for_vector.iterrows():
    course_name = row_value(row, "course_name")

    if not course_name:
        continue

    tracks = row.get("track_name")

    if isinstance(tracks, list):
        track_text = ", ".join(tracks)
    else:
        track_text = None

    desc = row_value(row, "course_description") or row_value(row, "course_description_track")

    lines = [
        f"[{row_value(row, 'dept_name')} 교과목 정보]",
        f"과목명: {course_name}",
        f"과목코드: {row_value(row, 'course_code')}",
        f"정규화 과목코드: {row_value(row, 'course_code_norm')}",
        f"과목수준: {row_value(row, 'course_level')}",
        f"이수구분: {row_value(row, 'course_type')}",
        f"학점: {row_value(row, 'credit')}",
        f"관련트랙: {track_text}",
        f"설명: {desc}",
        f"출처: {row_value(row, 'source_url')}",
    ]

    text = "\n".join([line for line in lines if not line.endswith("None")])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_course",
            "content_type": "course",
            "dept": row_value(row, "dept"),
            "dept_name": row_value(row, "dept_name"),
            "title": course_name,
            "course_code": row_value(row, "course_code"),
            "course_code_norm": row_value(row, "course_code_norm"),
            "course_level": row_value(row, "course_level"),
            "course_type": row_value(row, "course_type"),
            "tracks": track_text,
            "source_url": row_value(row, "source_url"),
            "crawled_at": row_value(row, "crawled_at"),
        },
        doc_id_seed=row_value(row, "course_id"),
    )


# ------------------------------------------------------------
# 4-3. people -> vector docs
# ------------------------------------------------------------

for _, row in people.iterrows():
    name = row_value(row, "name") or row_value(row, "name_ko") or row_value(row, "name_en")

    if not name:
        continue

    lines = [
        f"[{row_value(row, 'dept_name')} 교수진/구성원 정보]",
        f"이름: {name}",
        f"한국어 이름: {row_value(row, 'name_ko')}",
        f"영문 이름: {row_value(row, 'name_en')}",
        f"역할: {row_value(row, 'role')}",
        f"정규화 역할: {row_value(row, 'role_normalized')}",
        f"교원 그룹: {row_value(row, 'faculty_group')}",
        f"이메일: {row_value(row, 'email')}",
        f"전화번호: {row_value(row, 'phone')}",
        f"연구실/사무실: {row_value(row, 'office')}",
        f"연구분야: {row_value(row, 'research_area')}",
        f"홈페이지: {row_value(row, 'homepage')}",
        f"출처: {row_value(row, 'source_url')}",
    ]

    text = "\n".join([line for line in lines if not line.endswith("None")])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_person",
            "content_type": "person",
            "dept": row_value(row, "dept"),
            "dept_name": row_value(row, "dept_name"),
            "title": name,
            "name": name,
            "role": row_value(row, "role_normalized") or row_value(row, "role"),
            "email": row_value(row, "email"),
            "homepage": row_value(row, "homepage"),
            "source_url": row_value(row, "source_url") or row_value(row, "homepage"),
            "crawled_at": row_value(row, "crawled_at"),
        },
        doc_id_seed=row_value(row, "person_id") or row_value(row, "record_id"),
    )


# ------------------------------------------------------------
# 4-4. events -> vector docs
# ------------------------------------------------------------

for _, row in events.iterrows():
    title = row_value(row, "title") or "행사/공지 정보"

    lines = [
        f"[{row_value(row, 'dept_name')} 행사/공지 정보]",
        f"행사유형: {row_value(row, 'event_type')}",
        f"페이지 제목: {row_value(row, 'page_title')}",
        f"제목: {title}",
        f"일자: {row_value(row, 'event_date')}",
        f"요약: {row_value(row, 'summary')}",
        f"내용: {row_value(row, 'content')}",
        f"출처: {row_value(row, 'source_url')}",
    ]

    text = "\n".join([line for line in lines if not line.endswith("None")])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_event",
            "content_type": "event",
            "dept": row_value(row, "dept"),
            "dept_name": row_value(row, "dept_name"),
            "title": title,
            "event_date": row_value(row, "event_date"),
            "source_url": row_value(row, "source_url"),
            "crawled_at": row_value(row, "crawled_at"),
        },
        doc_id_seed=row_value(row, "event_id"),
    )


# ------------------------------------------------------------
# 4-5. KAIST profile/statistics/links -> vector docs
# ------------------------------------------------------------

for _, row in kaist_profile.iterrows():
    item = row_value(row, "item")
    content = row_value(row, "content")

    if not item and not content:
        continue

    text = "\n".join([
        "[KAIST 기본 정보]",
        f"항목: {item}",
        f"내용: {content}",
        f"비고: {row_value(row, 'note')}",
        f"출처: {row_value(row, 'source_url')}",
    ])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_kaist_profile",
            "content_type": "kaist_profile",
            "dept": None,
            "dept_name": "KAIST",
            "title": item,
            "source_url": row_value(row, "source_url"),
        },
        doc_id_seed=f"kaist_profile_{item}_{content}",
    )


for _, row in kaist_statistics.iterrows():
    stat_group = row_value(row, "stat_group")
    level = row_value(row, "level")

    text = "\n".join([
        "[KAIST 통계 정보]",
        f"통계그룹: {stat_group}",
        f"구분: {level}",
        f"값: {row_value(row, 'value_raw')}",
        f"숫자값: {row_value(row, 'value_number')}",
        f"비고: {row_value(row, 'note')}",
    ])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_kaist_statistics",
            "content_type": "kaist_statistics",
            "dept": None,
            "dept_name": "KAIST",
            "title": f"{stat_group} {level}",
            "source_url": kaist_home_url,
        },
        doc_id_seed=f"kaist_statistics_{stat_group}_{level}",
    )


for _, row in kaist_links.iterrows():
    link_name = row_value(row, "link_name")
    url = row_value(row, "url")

    if not url:
        continue

    text = "\n".join([
        "[KAIST 공식 링크]",
        f"링크명: {link_name}",
        f"URL: {url}",
        f"비고: {row_value(row, 'note')}",
    ])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_kaist_link",
            "content_type": "link",
            "dept": None,
            "dept_name": "KAIST",
            "title": link_name,
            "url": url,
            "source_url": kaist_home_url,
        },
        doc_id_seed=f"kaist_link_{link_name}_{url}",
    )


# ------------------------------------------------------------
# 4-6. department offices -> vector docs
# ------------------------------------------------------------

for _, row in department_offices.iterrows():
    program_name = row_value(row, "program_name")

    if not program_name:
        continue

    text = "\n".join([
        "[KAIST 학과사무실 정보]",
        f"프로그램/학과명: {program_name}",
        f"전화번호: {row_value(row, 'phone')}",
        f"웹사이트: {row_value(row, 'website')}",
        f"위치: {row_value(row, 'building_location')}",
        f"출처: {row_value(row, 'source_page')}",
    ])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_department_office",
            "content_type": "office_contact",
            "dept": None,
            "dept_name": program_name,
            "title": program_name,
            "phone": row_value(row, "phone"),
            "website": row_value(row, "website"),
            "source_url": row_value(row, "source_page"),
        },
        doc_id_seed=row_value(row, "office_id"),
    )


# ------------------------------------------------------------
# 4-7. assets -> vector docs
# ------------------------------------------------------------

for _, row in assets[assets["is_vector_candidate"] == True].iterrows():
    text_value = row_value(row, "text")

    if not text_value:
        continue

    lines = [
        f"[{row_value(row, 'dept_name')} 웹 자산/링크 정보]",
        f"카테고리: {row_value(row, 'category')}",
        f"주제: {row_value(row, 'topic')}",
        f"콘텐츠 타입: {row_value(row, 'content_type')}",
        f"자산 타입: {row_value(row, 'asset_type')}",
        f"내용: {text_value}",
        f"URL: {row_value(row, 'url')}",
        f"출처 페이지: {row_value(row, 'source_url')}",
    ]

    text = "\n".join([line for line in lines if not line.endswith("None")])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_asset",
            "content_type": row_value(row, "content_type"),
            "dept": row_value(row, "dept"),
            "dept_name": row_value(row, "dept_name"),
            "title": row_value(row, "topic") or row_value(row, "category"),
            "url": row_value(row, "url"),
            "source_url": row_value(row, "source_url"),
            "crawled_at": row_value(row, "crawled_at"),
        },
        doc_id_seed=row_value(row, "asset_id"),
    )


# ------------------------------------------------------------
# 4-8. attachments metadata -> vector docs
# ------------------------------------------------------------

for _, row in attachments.iterrows():
    filename = row_value(row, "filename")

    if not filename:
        continue

    text = "\n".join([
        "[KAIST 첨부파일 메타데이터]",
        f"학과 코드: {row_value(row, 'dept')}",
        f"학과명: {row_value(row, 'dept_name')}",
        f"게시판: {row_value(row, 'board')}",
        f"파일명: {filename}",
        f"파일 확장자: {row_value(row, 'ext')}",
        f"파일 크기: {row_value(row, 'size')}",
        f"다운로드 URL: {row_value(row, 'url')}",
        "주의: text_preview는 일부 미리보기이므로 vectorstore 본문으로 사용하지 않음.",
    ])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_attachment_meta",
            "content_type": "attachment_meta",
            "dept": row_value(row, "dept"),
            "dept_name": row_value(row, "dept_name"),
            "title": filename,
            "filename": filename,
            "url": row_value(row, "url"),
            "source_url": row_value(row, "source_url") or row_value(row, "url"),
            "crawled_at": row_value(row, "crawled_at"),
        },
        doc_id_seed=row_value(row, "attachment_id"),
    )


# ============================================================
# 5. PDF 추출
# ============================================================

def extract_pdf_text_pages(pdf_path: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        import fitz
    except ModuleNotFoundError:
        return [], "PyMuPDF가 설치되어 있지 않습니다. pip install pymupdf 실행이 필요합니다."

    if not pdf_path.exists():
        return [], "missing_file"

    pages: list[dict[str, Any]] = []

    try:
        with fitz.open(pdf_path) as document:
            for page_index, page in enumerate(document, start=1):
                text = page.get_text("text")
                text = clean_scalar(text)

                pages.append({
                    "page": page_index,
                    "text": text,
                    "char_len": len(text or ""),
                })
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"

    return pages, None


pdf_page_reports: list[dict[str, Any]] = []

for pdf_filename, pdf_meta in PDF_FILES.items():
    pdf_path = RAW_DATA_DIR / pdf_filename
    pages, error = extract_pdf_text_pages(pdf_path)

    if error == "missing_file":
        pdf_page_reports.append({
            "file_name": pdf_filename,
            "dept": pdf_meta["dept"],
            "dept_name": pdf_meta["dept_name"],
            "page": None,
            "status": "missing_file",
            "char_len": 0,
            "message": f"PDF 파일을 찾을 수 없습니다: {pdf_path}",
        })
        continue

    if error:
        pdf_page_reports.append({
            "file_name": pdf_filename,
            "dept": pdf_meta["dept"],
            "dept_name": pdf_meta["dept_name"],
            "page": None,
            "status": "error",
            "char_len": 0,
            "message": error,
        })
        continue

    for page_info in pages:
        page_no = page_info["page"]
        page_text = page_info["text"]
        char_len = page_info["char_len"]

        if not page_text or char_len < 40:
            pdf_page_reports.append({
                "file_name": pdf_filename,
                "dept": pdf_meta["dept"],
                "dept_name": pdf_meta["dept_name"],
                "page": page_no,
                "status": "empty_or_too_short",
                "char_len": char_len,
                "message": "텍스트가 없거나 너무 짧습니다.",
            })
            continue

        chunks = chunk_text_by_paragraphs(page_text, max_chars=1200, overlap_chars=120)

        for chunk_index, chunk in enumerate(chunks, start=1):
            add_doc(
                vector_docs,
                "\n".join([
                    f"[{pdf_meta['dept_name']} PDF 문서]",
                    f"파일명: {pdf_filename}",
                    f"문서유형: {pdf_meta['document_type']}",
                    f"페이지: {page_no}",
                    f"청크: {chunk_index}",
                    chunk,
                ]),
                {
                    "source_type": "pdf",
                    "content_type": f"pdf_{pdf_meta['document_type']}",
                    "dept": pdf_meta["dept"],
                    "dept_name": pdf_meta["dept_name"],
                    "title": pdf_filename,
                    "file_name": pdf_filename,
                    "page": page_no,
                    "chunk_index": chunk_index,
                    "document_type": pdf_meta["document_type"],
                    "source_url": pdf_meta["source_url"],
                    "year": pdf_meta["year"],
                    "semester": pdf_meta["semester"],
                },
                doc_id_seed=f"{pdf_filename}_{page_no}_{chunk_index}",
            )

        pdf_page_reports.append({
            "file_name": pdf_filename,
            "dept": pdf_meta["dept"],
            "dept_name": pdf_meta["dept_name"],
            "page": page_no,
            "status": "ok",
            "char_len": char_len,
            "message": f"{len(chunks)} chunks",
        })


pdf_report_df = pd.DataFrame(pdf_page_reports)
save_csv(pdf_report_df, REPORT_DIR / "pdf_page_report.csv")


# ============================================================
# 5-1. PDF 추출 결과 검증 + text_preview fallback
# ============================================================

pdf_doc_count = sum(
    1 for doc in vector_docs
    if doc["metadata"].get("source_type") == "pdf"
)

print("\n[PDF 추출 검증]")
print(f"- PDF vector 문서 수: {pdf_doc_count}")

if len(pdf_report_df) > 0 and "status" in pdf_report_df.columns:
    print("- PDF 페이지 상태 분포:")
    print(pdf_report_df["status"].value_counts(dropna=False).to_string())

print(f"- PDF 페이지 리포트 저장 위치: {REPORT_DIR / 'pdf_page_report.csv'}")

fallback_preview_count = 0

if pdf_doc_count == 0:
    print("[경고] PDF 본문 추출 결과가 없습니다. attachments.text_preview를 fallback 문서로 추가합니다.")

    if "text_preview" in attachments.columns:
        for _, row in attachments.iterrows():
            preview = row_value(row, "text_preview")
            filename = row_value(row, "filename")

            if not preview:
                continue

            add_doc(
                vector_docs,
                "\n".join([
                    "[KAIST 첨부파일 미리보기]",
                    f"학과 코드: {row_value(row, 'dept')}",
                    f"학과명: {row_value(row, 'dept_name')}",
                    f"파일명: {filename}",
                    f"내용 미리보기: {preview}",
                    f"다운로드 URL: {row_value(row, 'url')}",
                    f"출처 페이지: {row_value(row, 'source_url')}",
                ]),
                {
                    "source_type": "csv_attachment_preview",
                    "content_type": "attachment_preview",
                    "dept": row_value(row, "dept"),
                    "dept_name": row_value(row, "dept_name"),
                    "title": filename,
                    "filename": filename,
                    "url": row_value(row, "url"),
                    "source_url": row_value(row, "source_url") or row_value(row, "url"),
                    "crawled_at": row_value(row, "crawled_at"),
                },
                doc_id_seed=f"attachment_preview_{row_value(row, 'attachment_id') or filename}",
            )

            fallback_preview_count += 1

    print(f"- fallback preview 문서 수: {fallback_preview_count}")

if pdf_doc_count == 0 and fallback_preview_count == 0:
    raise RuntimeError(
        "PDF 본문도 추출되지 않았고 attachments.text_preview fallback도 생성되지 않았습니다. "
        "RAW_DATA_DIR의 PDF 파일명, PDF_FILES 설정, attachments.csv의 text_preview를 확인하세요."
    )


# ============================================================
# 6. 중복 제거 및 Vector JSON 저장
# ============================================================

deduped_docs: list[dict[str, Any]] = []
seen_doc_ids: set[str] = set()
seen_hashes: set[str] = set()

for doc in vector_docs:
    text = doc.get("text", "")
    metadata = doc.get("metadata", {}) or {}
    doc_hash = make_hash(
        metadata.get("source_type"),
        metadata.get("content_type"),
        metadata.get("dept"),
        metadata.get("title"),
        text,
        length=24,
    )

    if doc_hash in seen_hashes:
        continue

    doc_id = doc.get("id") or doc_hash

    if doc_id in seen_doc_ids:
        doc_id = doc_hash
        doc["id"] = doc_id

    seen_doc_ids.add(doc_id)
    seen_hashes.add(doc_hash)
    deduped_docs.append(doc)

vector_docs = deduped_docs


# ============================================================
# 6-1. vector 문서 품질 리포트 저장
# ============================================================

vector_quality_rows: list[dict[str, Any]] = []

for doc in vector_docs:
    meta = doc.get("metadata", {}) or {}

    vector_quality_rows.append({
        "id": doc.get("id"),
        "source_type": meta.get("source_type"),
        "content_type": meta.get("content_type"),
        "dept": meta.get("dept"),
        "dept_name": meta.get("dept_name"),
        "title": meta.get("title"),
        "source_url": meta.get("source_url"),
        "text_length": len(doc.get("text", "") or ""),
    })

vector_quality_df = pd.DataFrame(vector_quality_rows)

if len(vector_quality_df) > 0:
    save_csv(vector_quality_df, REPORT_DIR / "vector_documents_quality.csv")

    content_type_report = (
        vector_quality_df
        .groupby(["source_type", "content_type"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    save_csv(content_type_report, REPORT_DIR / "vector_content_type_report.csv")

    dept_report = (
        vector_quality_df
        .groupby(["dept", "dept_name"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    save_csv(dept_report, REPORT_DIR / "vector_dept_report.csv")

    print("\n[Vector 문서 분포]")
    print("- source_type/content_type 분포:")
    print(content_type_report.head(30).to_string(index=False))

    print("\n- 학과별 vector 문서 수:")
    print(dept_report.to_string(index=False))


vector_json_path = VECTOR_DIR / "vector_documents.json"
with open(vector_json_path, "w", encoding="utf-8") as file:
    json.dump(vector_docs, file, ensure_ascii=False, indent=2)

vector_jsonl_path = VECTOR_DIR / "vector_documents.jsonl"
with open(vector_jsonl_path, "w", encoding="utf-8") as file:
    for doc in vector_docs:
        file.write(json.dumps(doc, ensure_ascii=False) + "\n")


# ============================================================
# 7. 전처리 요약 리포트 저장
# ============================================================

summary_rows: list[dict[str, Any]] = []

for file in SQL_DIR.glob("*.csv"):
    try:
        temp_df = pd.read_csv(file, dtype=str, encoding="utf-8-sig")
        row_count = len(temp_df)
        col_count = len(temp_df.columns)
    except Exception:
        row_count = None
        col_count = None

    summary_rows.append({
        "output_type": "sql_csv",
        "file_name": file.name,
        "path": str(file),
        "row_count": row_count,
        "column_count": col_count,
    })

summary_rows.append({
    "output_type": "vector_json",
    "file_name": vector_json_path.name,
    "path": str(vector_json_path),
    "row_count": len(vector_docs),
    "column_count": None,
})

summary_rows.append({
    "output_type": "vector_jsonl",
    "file_name": vector_jsonl_path.name,
    "path": str(vector_jsonl_path),
    "row_count": len(vector_docs),
    "column_count": None,
})

summary_df = pd.DataFrame(summary_rows)
save_csv(summary_df, REPORT_DIR / "preprocess_summary.csv")


# ============================================================
# 8. 결과 확인
# ============================================================

print("\n========== 전처리 완료 ==========")
print(f"SQL CSV 저장 폴더: {SQL_DIR}")
print(f"VectorStore JSON 저장 파일: {vector_json_path}")
print(f"VectorStore JSONL 저장 파일: {vector_jsonl_path}")
print(f"PDF 페이지 추출 리포트: {REPORT_DIR / 'pdf_page_report.csv'}")
print(f"Vector 문서 품질 리포트: {REPORT_DIR / 'vector_documents_quality.csv'}")
print(f"Vector content_type 리포트: {REPORT_DIR / 'vector_content_type_report.csv'}")
print(f"Vector 학과별 리포트: {REPORT_DIR / 'vector_dept_report.csv'}")
print(f"전체 요약 리포트: {REPORT_DIR / 'preprocess_summary.csv'}")
print(f"Vector 문서 수: {len(vector_docs)}")

print("\n[SQL CSV 목록]")
for file in sorted(SQL_DIR.glob("*.csv")):
    print("-", file.name)

print("\n[주의]")
print("1. quality_report.csv는 RAG 지식이 아니라 관리용 로그로 그대로 저장했습니다.")
print("2. attachments_clean의 text_preview는 기본적으로 vectorstore에 넣지 않습니다.")
print("3. 단, PDF 본문 추출이 0개면 text_preview를 fallback 문서로 추가합니다.")
print("4. course_track_map은 SQL에는 별도 저장했고, vectorstore에는 courses와 합쳐서 과목 문서로 만들었습니다.")
print("5. assets의 image-only 행은 SQL에는 남기고 vectorstore에서는 제외했습니다.")
print("6. pdf_page_report.csv에서 missing_file 또는 empty_or_too_short가 많으면 PDF 경로/OCR 처리가 필요합니다.")