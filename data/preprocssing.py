# ============================================================
# KAIST 대학원 RAG Agent용 14개 파일 전처리 코드
# - SQL 적재용 CSV 생성
# - VectorStore 적재용 JSON 생성
# ============================================================

# 필요 패키지
# !pip install pandas pymupdf

import re
import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime

import pandas as pd


# ============================================================
# 0. 경로 설정
# ============================================================

# 파일들이 들어있는 폴더로 바꾸세요.
# 예: BASE_DIR = Path(r"C:\Users\Playdata\workspace\kaist_data")
BASE_DIR = Path(r"C:\Users\Playdata\workspace\SKN28-third-2TEAM\data\raw_data")  

OUT_DIR = BASE_DIR.parent / "processed"
SQL_DIR = OUT_DIR / "sql"
VECTOR_DIR = OUT_DIR / "vectorstore"
REPORT_DIR = OUT_DIR / "reports"

for d in [SQL_DIR, VECTOR_DIR, REPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)


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


def is_empty(value) -> bool:
    if value is None:
        return True
    if pd.isna(value):
        return True
    text = str(value).strip()
    return text.lower() in NULL_LIKE


def clean_scalar(value):
    """셀 하나 정리"""
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
    """CSV 공통 정리: 컬럼명 정리, 공백 정리, 완전 빈 행 제거"""
    df = df.copy()

    df.columns = [
        clean_scalar(col) if clean_scalar(col) else f"unnamed_{i}"
        for i, col in enumerate(df.columns)
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


def save_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def make_hash(*parts, length=16) -> str:
    raw = "||".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def row_value(row, col):
    if col not in row:
        return None
    value = row[col]
    return None if is_empty(value) else str(value).strip()


def recompute_missing_fields(df: pd.DataFrame, exclude=("missing_fields",)) -> pd.DataFrame:
    """기존 missing_fields가 틀린 경우가 있어 실제 값 기준으로 다시 계산"""
    df = df.copy()
    target_cols = [c for c in df.columns if c not in exclude]

    missing_values = []
    for _, row in df.iterrows():
        missing = [c for c in target_cols if is_empty(row.get(c))]
        missing_values.append(", ".join(missing) if missing else None)

    df["missing_fields"] = missing_values
    return df


def normalize_email(value):
    if is_empty(value):
        return None

    text = str(value).strip()
    text = text.replace("mailto:", "")
    text = text.replace("MAILTO:", "")
    text = text.strip()

    # 이메일만 추출
    match = re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else text


def normalize_course_code(value):
    if is_empty(value):
        return None

    text = str(value).strip()
    text = re.sub(r"[^A-Za-z0-9가-힣]", "", text)
    return text.upper() if text else None


def normalize_date_yyyy_mm_dd(value):
    if is_empty(value):
        return None

    text = str(value).strip()

    # 이미 YYYY-MM-DD인 경우
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text

    # 2026. 03. 27 같은 형식
    m = re.search(r"(20\d{2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})", text)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"

    return None


def extract_min_gpa(*values):
    joined = " ".join(str(v) for v in values if not is_empty(v))

    # 3.7 같은 값이 학점 조건으로 들어간 경우
    patterns = [
        r"평점평균.{0,20}?(\d\.\d)",
        r"누적\s*평점.{0,20}?(\d\.\d)",
        r"GPA.{0,20}?(\d\.\d)",
        r"(\d\.\d)\s*이상",
    ]

    for pat in patterns:
        m = re.search(pat, joined, flags=re.IGNORECASE)
        if m:
            return m.group(1)

    return None


def make_vector_doc(text: str, metadata: dict, doc_id_seed=None):
    text = clean_scalar(text)
    if not text:
        return None

    metadata = {
        k: (None if is_empty(v) else v)
        for k, v in metadata.items()
    }

    doc_id = make_hash(
        doc_id_seed or metadata.get("source_type"),
        metadata.get("dept"),
        metadata.get("title"),
        metadata.get("page"),
        text[:300],
        length=20,
    )

    return {
        "id": doc_id,
        "text": text,
        "metadata": metadata,
    }


def add_doc(docs, text, metadata, doc_id_seed=None):
    doc = make_vector_doc(text, metadata, doc_id_seed=doc_id_seed)
    if doc:
        docs.append(doc)


def chunk_text_by_paragraphs(text, max_chars=1200, overlap_chars=120):
    text = clean_scalar(text)
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        candidate = current + "\n\n" + para if current else para

        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())

            # 너무 긴 문단은 강제 분할
            if len(para) > max_chars:
                start = 0
                while start < len(para):
                    end = start + max_chars
                    chunks.append(para[start:end].strip())
                    start = end - overlap_chars
                    if start < 0:
                        start = 0
                    if start >= len(para):
                        break
                current = ""
            else:
                overlap = current[-overlap_chars:] if current else ""
                current = (overlap + "\n\n" + para).strip() if overlap else para

    if current:
        chunks.append(current.strip())

    return chunks


# ============================================================
# 2. CSV 로드
# ============================================================

dfs = {}
for key, filename in CSV_FILES.items():
    path = BASE_DIR / filename
    dfs[key] = read_csv_clean(path)
    print(f"[로드 완료] {key}: {dfs[key].shape} - {filename}")


# ============================================================
# 3. SQL 적재용 CSV 생성
# ============================================================

# ------------------------------------------------------------
# 3-1. admissions
# ------------------------------------------------------------

admissions = dfs["admissions"].copy()

type_map = {
    "admission_eligibility": "eligibility",
    "admission_schedule": "schedule",
    "admission_schedule_or_process": "schedule",
    "scholarship": "scholarship",
    "advisor_matching": "advisor_matching",
    "admission_info": "general_info",
}

admissions["admission_type_norm"] = admissions["admission_type"].map(
    lambda x: type_map.get(x, x)
)

# schedule_date에 3.7 같은 학점값이 들어간 경우 분리
admissions["schedule_date_raw"] = admissions.get("schedule_date")
admissions["schedule_date"] = admissions["schedule_date_raw"].map(normalize_date_yyyy_mm_dd)

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

courses = dfs["courses"].copy()
courses["course_code_norm"] = courses["course_code"].map(normalize_course_code)

courses["course_id"] = courses.apply(
    lambda row: row.get("record_id") or make_hash(
        row.get("dept"),
        row.get("course_code_norm"),
        row.get("course_name"),
    ),
    axis=1,
)

courses = courses.drop_duplicates(
    subset=["dept", "course_code_norm", "course_name", "course_type"],
    keep="first",
).reset_index(drop=True)

courses = recompute_missing_fields(courses)
save_csv(courses, SQL_DIR / "courses.csv")


# ------------------------------------------------------------
# 3-3. course_track_map
# ------------------------------------------------------------

course_track_map = dfs["course_track_map"].copy()
course_track_map["course_code_norm"] = course_track_map["course_code"].map(normalize_course_code)

course_track_map["course_track_id"] = course_track_map.apply(
    lambda row: make_hash(
        row.get("dept"),
        row.get("course_code_norm"),
        row.get("course_name"),
        row.get("track_name"),
    ),
    axis=1,
)

course_track_map = course_track_map.drop_duplicates(
    subset=["dept", "course_code_norm", "course_name", "track_name"],
    keep="first",
).reset_index(drop=True)

course_track_map = recompute_missing_fields(course_track_map)
save_csv(course_track_map, SQL_DIR / "course_track_map.csv")


# ------------------------------------------------------------
# 3-4. people
# ------------------------------------------------------------

people = dfs["people"].copy()

people["email"] = people["email"].map(normalize_email)
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

people = people.drop_duplicates(
    subset=["dept", "name", "email", "homepage"],
    keep="first",
).reset_index(drop=True)

people = recompute_missing_fields(people)
save_csv(people, SQL_DIR / "people.csv")


# ------------------------------------------------------------
# 3-5. events
# ------------------------------------------------------------

events = dfs["events"].copy()
events["event_date"] = events["event_date"].map(normalize_date_yyyy_mm_dd)

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

assets = dfs["assets"].copy()

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

# vectorstore 후보 여부
# image만 있는 행은 SQL에는 남기되 vectorstore에는 넣지 않음
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

attachments = dfs["attachments"].copy()

attachments["attachment_id"] = attachments.apply(
    lambda row: make_hash(
        row.get("dept"),
        row.get("filename"),
        row.get("url"),
    ),
    axis=1,
)

# text_preview는 일부 미리보기라 vectorstore용 원문으로 쓰지 않음
attachments["use_text_preview_for_vectorstore"] = False

# 실제 업로드된 PDF를 별도 추출해서 vectorstore에 넣을 예정
attachments["note"] = "PDF 원문은 업로드된 PDF 파일에서 직접 추출. text_preview는 부분 미리보기라 vectorstore 제외."

attachments = recompute_missing_fields(attachments)
save_csv(attachments, SQL_DIR / "attachments.csv")


# ------------------------------------------------------------
# 3-8. quality_report
# ------------------------------------------------------------

# 품질 리포트는 전처리할 필요 없음.
# RAG 지식으로 쓰지 않고 관리/점검용 SQL 테이블로만 그대로 저장.
quality_report = dfs["quality_report"].copy()
save_csv(quality_report, SQL_DIR / "quality_report.csv")


# ------------------------------------------------------------
# 3-9. KAIST 기본정보
# ------------------------------------------------------------

basic = dfs["kaist_basic_info"].copy()
basic = basic.dropna(how="all").reset_index(drop=True)

kaist_home_url = None
if "항목" in basic.columns and "내용" in basic.columns:
    url_rows = basic[basic["항목"] == "URL"]
    if len(url_rows) > 0:
        kaist_home_url = url_rows.iloc[0]["내용"]

# 링크 정보
kaist_links = basic[
    basic["내용"].fillna("").str.contains(r"https?://", regex=True)
].copy()
kaist_links = kaist_links.rename(columns={"항목": "link_name", "내용": "url", "기타": "note"})
kaist_links["source"] = "KAIST 공식홈페이지 조사"
save_csv(kaist_links, SQL_DIR / "kaist_links.csv")


# 통계 정보
stat_rows = []
current_group = None
stat_group_names = {"졸업생", "재학생", "교직원"}

for _, row in basic.iterrows():
    item = row.get("항목")
    value = row.get("내용")
    note = row.get("기타")

    if is_empty(item) or is_empty(value):
        continue

    if item in stat_group_names:
        current_group = item
        stat_rows.append({
            "stat_group": current_group,
            "level": "전체",
            "value_raw": value,
            "value_number": re.sub(r"[^0-9]", "", value) or None,
            "note": note,
            "source": "KAIST 공식홈페이지 조사",
        })
    elif current_group and item in {"학사", "석사", "석박통합", "박사", "교수", "직원"}:
        stat_rows.append({
            "stat_group": current_group,
            "level": item,
            "value_raw": value,
            "value_number": re.sub(r"[^0-9]", "", value) or None,
            "note": note,
            "source": "KAIST 공식홈페이지 조사",
        })

kaist_statistics = pd.DataFrame(stat_rows)
save_csv(kaist_statistics, SQL_DIR / "kaist_statistics.csv")


# 프로필 정보
stat_items = {"졸업생", "재학생", "교직원", "학사", "석사", "석박통합", "박사", "교수", "직원"}
profile = basic.copy()
profile = profile[~profile["항목"].isin(stat_items)]
profile = profile[~profile["내용"].fillna("").str.contains(r"https?://", regex=True)]
profile = profile.dropna(how="all").reset_index(drop=True)
profile = profile.rename(columns={"항목": "item", "내용": "content", "기타": "note"})
profile["source_url"] = kaist_home_url
profile["source"] = "KAIST 공식홈페이지 조사"

save_csv(profile, SQL_DIR / "kaist_profile.csv")


# ------------------------------------------------------------
# 3-10. 학과사무실
# ------------------------------------------------------------

office_raw_path = BASE_DIR / CSV_FILES["department_offices"]
office_raw = pd.read_csv(office_raw_path, dtype=str, encoding="utf-8-sig")

source_note = str(office_raw.columns[0]).strip()

# 실제 헤더가 들어있는 행 찾기
header_idx = None
for idx, row in office_raw.iterrows():
    first_value = clean_scalar(row.iloc[0])
    if first_value == "학과/프로그램":
        header_idx = idx
        break

if header_idx is None:
    raise ValueError("학과사무실 파일에서 '학과/프로그램' 헤더 행을 찾지 못했습니다.")

offices = office_raw.iloc[header_idx + 1:, :4].copy()
offices.columns = ["program_name", "phone", "website", "building_location"]
offices = clean_dataframe(offices)

offices["office_id"] = offices.apply(
    lambda row: make_hash(
        row.get("program_name"),
        row.get("phone"),
        row.get("website"),
        row.get("building_location"),
    ),
    axis=1,
)

offices["source"] = source_note
offices["source_page"] = "p22-23"

offices = recompute_missing_fields(offices)
save_csv(offices, SQL_DIR / "department_offices.csv")


# ============================================================
# 4. VectorStore용 JSON 문서 생성
# ============================================================

vector_docs = []


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

    text = "\n".join([x for x in lines if not x.endswith("None")])

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

track_group = (
    course_track_map
    .groupby(["dept", "course_code_norm"], dropna=False)
    .agg({
        "track_name": lambda x: sorted(set(v for v in x if not is_empty(v))),
        "course_description": lambda x: next((v for v in x if not is_empty(v)), None),
    })
    .reset_index()
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
        f"과목 수준: {row_value(row, 'course_level')}",
        f"이수구분: {row_value(row, 'course_type')}",
        f"학점: {row_value(row, 'credit')}",
        f"관련 트랙: {track_text}",
        f"설명: {desc}",
        f"출처: {row_value(row, 'source_url')}",
    ]

    text = "\n".join([x for x in lines if not x.endswith("None")])

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
            "course_type": row_value(row, "course_type"),
            "course_level": row_value(row, "course_level"),
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
    name = row_value(row, "name")
    if not name:
        continue

    lines = [
        f"[{row_value(row, 'dept_name')} 교수/구성원 정보]",
        f"이름: {name}",
        f"한글명: {row_value(row, 'name_ko')}",
        f"영문명: {row_value(row, 'name_en')}",
        f"역할: {row_value(row, 'role')}",
        f"역할 정규화: {row_value(row, 'role_normalized')}",
        f"교원 그룹: {row_value(row, 'faculty_group')}",
        f"이메일: {row_value(row, 'email')}",
        f"전화번호: {row_value(row, 'phone')}",
        f"연구실/사무실: {row_value(row, 'office')}",
        f"연구분야: {row_value(row, 'research_area')}",
        f"홈페이지: {row_value(row, 'homepage')}",
        f"출처: {row_value(row, 'source_url')}",
    ]

    text = "\n".join([x for x in lines if not x.endswith("None")])

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
            "role": row_value(row, "role_normalized"),
            "email": row_value(row, "email"),
            "homepage": row_value(row, "homepage"),
            "source_url": row_value(row, "source_url"),
            "crawled_at": row_value(row, "crawled_at"),
        },
        doc_id_seed=row_value(row, "person_id"),
    )


# ------------------------------------------------------------
# 4-4. events -> vector docs
# ------------------------------------------------------------

for _, row in events.iterrows():
    title = row_value(row, "title") or "행사 정보"

    lines = [
        f"[{row_value(row, 'dept_name')} 행사/공지 정보]",
        f"행사 유형: {row_value(row, 'event_type')}",
        f"페이지 제목: {row_value(row, 'page_title')}",
        f"제목: {title}",
        f"행사일: {row_value(row, 'event_date')}",
        f"요약: {row_value(row, 'summary')}",
        f"내용: {row_value(row, 'content')}",
        f"출처: {row_value(row, 'source_url')}",
    ]

    text = "\n".join([x for x in lines if not x.endswith("None")])

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
# 4-5. department_offices -> vector docs
# ------------------------------------------------------------

for _, row in offices.iterrows():
    program = row_value(row, "program_name")
    if not program:
        continue

    text = "\n".join([
        "[KAIST 학과사무실 정보]",
        f"학과/프로그램: {program}",
        f"전화번호: {row_value(row, 'phone')}",
        f"웹사이트: {row_value(row, 'website')}",
        f"건물 위치: {row_value(row, 'building_location')}",
        f"출처: {row_value(row, 'source')}",
    ])

    add_doc(
        vector_docs,
        text,
        {
            "source_type": "csv_department_office",
            "content_type": "office_contact",
            "dept": None,
            "dept_name": program,
            "title": program,
            "phone": row_value(row, "phone"),
            "website": row_value(row, "website"),
            "source": row_value(row, "source"),
            "source_page": row_value(row, "source_page"),
        },
        doc_id_seed=row_value(row, "office_id"),
    )


# ------------------------------------------------------------
# 4-6. KAIST 기본정보 -> vector docs
# ------------------------------------------------------------

# 학교 프로필은 하나의 문서로 묶음
profile_lines = ["[KAIST 기본정보]"]
for _, row in profile.iterrows():
    item = row_value(row, "item")
    content = row_value(row, "content")
    if item and content:
        profile_lines.append(f"{item}: {content}")

add_doc(
    vector_docs,
    "\n".join(profile_lines),
    {
        "source_type": "csv_kaist_profile",
        "content_type": "kaist_profile",
        "dept": None,
        "dept_name": "KAIST",
        "title": "KAIST 기본정보",
        "source_url": kaist_home_url,
    },
    doc_id_seed="kaist_profile",
)

# 통계도 하나의 문서로 묶음
if len(kaist_statistics) > 0:
    stat_lines = ["[KAIST 통계 정보]"]
    for _, row in kaist_statistics.iterrows():
        stat_lines.append(
            f"{row_value(row, 'stat_group')} - {row_value(row, 'level')}: "
            f"{row_value(row, 'value_raw')} ({row_value(row, 'note')})"
        )

    add_doc(
        vector_docs,
        "\n".join(stat_lines),
        {
            "source_type": "csv_kaist_statistics",
            "content_type": "kaist_statistics",
            "dept": None,
            "dept_name": "KAIST",
            "title": "KAIST 통계 정보",
            "source_url": kaist_home_url,
        },
        doc_id_seed="kaist_statistics",
    )

# 링크 정보
for _, row in kaist_links.iterrows():
    link_name = row_value(row, "link_name")
    url = row_value(row, "url")
    if not link_name or not url:
        continue

    text = "\n".join([
        "[KAIST 공식 링크]",
        f"항목: {link_name}",
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
# 4-7. assets -> vector docs
# ------------------------------------------------------------

# image만 있는 행은 제외.
# 연락처, 링크, 의미 있는 텍스트만 vectorstore에 넣음.
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

    text = "\n".join([x for x in lines if not x.endswith("None")])

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

# PDF 본문은 실제 PDF에서 추출하므로, 여기서는 "첨부파일 존재/다운로드 링크" 정도만 문서화
for _, row in attachments.iterrows():
    filename = row_value(row, "filename")
    if not filename:
        continue

    text = "\n".join([
        "[KAIST 첨부파일 메타데이터]",
        f"학과 코드: {row_value(row, 'dept')}",
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
            "dept_name": None,
            "title": filename,
            "filename": filename,
            "url": row_value(row, "url"),
            "source_url": row_value(row, "url"),
            "crawled_at": row_value(row, "crawled_at"),
        },
        doc_id_seed=row_value(row, "attachment_id"),
    )


# ============================================================
# 5. PDF 4개 추출 -> vector docs
# ============================================================

try:
    import fitz  # PyMuPDF
except ImportError as e:
    raise ImportError(
        "PDF 텍스트 추출을 위해 PyMuPDF가 필요합니다. "
        "아래 명령어를 먼저 실행하세요:\n\npip install pymupdf"
    ) from e


SECTION_RULES = [
    ("admission", ["입학", "지원 자격", "모집", "전형", "합격자", "원서접수", "Application", "Admission"]),
    ("schedule", ["일정", "Schedule", "Date", "지원일정"]),
    ("faculty", ["교수", "Faculty", "전임", "겸임", "학과장"]),
    ("curriculum", ["교육과정", "교과", "Curriculum", "Course", "Degree", "credits", "학점"]),
    ("research", ["연구", "Research", "분야", "AI 반도체", "AI 시스템", "거버넌스", "지속가능"]),
    ("vision", ["비전", "Vision", "목표", "왜", "paradigm", "Full Stack", "Human-Centered"]),
    ("advisor_matching", ["지도교수", "매칭", "장학생", "KAIST 장학생", "국비"]),
]


def detect_section(text):
    text = text or ""
    for section, keywords in SECTION_RULES:
        for kw in keywords:
            if kw.lower() in text.lower():
                return section
    return "general"


def extract_page_title(text):
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]

    skip_patterns = [
        r"^https?://",
        r"^\d+/\d+$",
        r"^\d{2}\.",
        r"^KAIST$",
    ]

    for line in lines[:10]:
        if any(re.search(pat, line) for pat in skip_patterns):
            continue
        if len(line) >= 2:
            return line[:120]

    return None


def extract_pdf_docs(pdf_path: Path, base_meta: dict):
    pdf_docs = []
    page_reports = []

    if not pdf_path.exists():
        page_reports.append({
            "file_name": pdf_path.name,
            "page": None,
            "status": "missing_file",
            "text_length": 0,
            "note": "파일 없음",
        })
        return pdf_docs, page_reports

    doc = fitz.open(pdf_path)

    for page_index in range(len(doc)):
        page_no = page_index + 1
        page = doc[page_index]

        raw_text = page.get_text("text")
        text = clean_scalar(raw_text)

        if not text or len(text) < 10:
            page_reports.append({
                "file_name": pdf_path.name,
                "page": page_no,
                "status": "empty_or_too_short",
                "text_length": len(text or ""),
                "note": "텍스트 레이어가 없거나 너무 짧음. 필요하면 OCR 검토.",
            })
            continue

        section = detect_section(text)
        title = extract_page_title(text) or f"{pdf_path.stem} page {page_no}"

        chunks = chunk_text_by_paragraphs(text, max_chars=1200, overlap_chars=120)

        for chunk_idx, chunk in enumerate(chunks, start=1):
            vector_text = "\n".join([
                f"[{base_meta['dept_name']} PDF 자료]",
                f"문서명: {pdf_path.name}",
                f"페이지: {page_no}",
                f"섹션: {section}",
                f"제목: {title}",
                "",
                chunk,
            ])

            metadata = {
                "source_type": "pdf",
                "content_type": f"pdf_{section}",
                "document_type": base_meta.get("document_type"),
                "dept": base_meta.get("dept"),
                "dept_name": base_meta.get("dept_name"),
                "file_name": pdf_path.name,
                "title": title,
                "section": section,
                "page": page_no,
                "chunk_index": chunk_idx,
                "source_url": base_meta.get("source_url"),
                "year": base_meta.get("year"),
                "semester": base_meta.get("semester"),
            }

            add_doc(
                pdf_docs,
                vector_text,
                metadata,
                doc_id_seed=f"{pdf_path.name}_{page_no}_{chunk_idx}",
            )

        page_reports.append({
            "file_name": pdf_path.name,
            "page": page_no,
            "status": "ok",
            "text_length": len(text),
            "section": section,
            "title": title,
            "chunk_count": len(chunks),
        })

    doc.close()
    return pdf_docs, page_reports


pdf_page_reports = []

for pdf_filename, meta in PDF_FILES.items():
    pdf_path = BASE_DIR / pdf_filename
    docs_from_pdf, reports = extract_pdf_docs(pdf_path, meta)
    vector_docs.extend(docs_from_pdf)
    pdf_page_reports.extend(reports)

pdf_report_df = pd.DataFrame(pdf_page_reports)
save_csv(pdf_report_df, REPORT_DIR / "pdf_page_report.csv")


# ============================================================
# 6. vector docs 중복 제거 및 저장
# ============================================================

deduped_docs = []
seen = set()

for doc in vector_docs:
    text = doc["text"]
    meta = doc["metadata"]

    key = make_hash(
        meta.get("source_type"),
        meta.get("dept"),
        meta.get("title"),
        meta.get("page"),
        text[:500],
        length=24,
    )

    if key in seen:
        continue

    seen.add(key)
    deduped_docs.append(doc)

vector_docs = deduped_docs


vector_json_path = VECTOR_DIR / "vector_documents.json"

with open(vector_json_path, "w", encoding="utf-8") as f:
    json.dump(vector_docs, f, ensure_ascii=False, indent=2)


# LangChain Document 로딩용 JSONL도 같이 저장하고 싶으면 아래 파일을 사용
vector_jsonl_path = VECTOR_DIR / "vector_documents.jsonl"

with open(vector_jsonl_path, "w", encoding="utf-8") as f:
    for doc in vector_docs:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")


# ============================================================
# 7. 전처리 요약 리포트 저장
# ============================================================

summary_rows = []

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
print(f"전체 요약 리포트: {REPORT_DIR / 'preprocess_summary.csv'}")
print(f"Vector 문서 수: {len(vector_docs)}")

print("\n[SQL CSV 목록]")
for file in sorted(SQL_DIR.glob("*.csv")):
    print("-", file.name)

print("\n[주의]")
print("1. quality_report.csv는 RAG 지식이 아니라 관리용 로그로 그대로 저장했습니다.")
print("2. attachments_clean의 text_preview는 vectorstore에 넣지 않고, 실제 PDF 4개에서 직접 텍스트를 추출했습니다.")
print("3. course_track_map은 SQL에는 별도 저장했고, vectorstore에는 courses와 합쳐서 과목 문서로 만들었습니다.")
print("4. assets의 image-only 행은 SQL에는 남기고 vectorstore에서는 제외했습니다.")
print("5. pdf_page_report.csv에서 empty_or_too_short가 많으면 OCR 처리가 추가로 필요합니다.")