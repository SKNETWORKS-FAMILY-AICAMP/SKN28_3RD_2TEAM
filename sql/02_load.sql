-- =====================================================================
--  KAIST AI대학 데이터 적재 (ETL)
--  방식: CSV ─LOAD DATA→ 스테이징(원본 그대로) ─INSERT...SELECT→ 정규화 테이블
--  실행: 01_schema.sql 로 테이블을 먼저 만든 뒤 이 파일을 실행한다.
-- =====================================================================

USE kaist_ai;

-- LOAD DATA LOCAL INFILE 를 쓰려면 서버 쪽 스위치를 켜야 한다.
-- (클라이언트 쪽은 mysql 실행 시 --local-infile=1 플래그로 켠다)
-- SET GLOBAL local_infile = 1;  -- SUPER 권한 필요; --local-infile=1 클라이언트 플래그로 대체

-- 여러 INSERT 동안 외래키 검사를 잠시 끈다.
-- 적재 순서를 신경 덜 쓰려는 ETL 관용수법. 끝에서 다시 켜고 무결성은 검증 쿼리로 확인.
SET FOREIGN_KEY_CHECKS = 0;


-- =====================================================================
--  STEP 1. 스테이징 테이블 — CSV 컬럼을 '그대로' 받는 임시 적재소
--          모든 컬럼을 TEXT 로 둔다: 타입 변환은 나중에 INSERT...SELECT 에서.
--          (원본을 손대지 않고 받은 뒤 변환하는 게 ETL 의 정석)
-- =====================================================================
DROP TABLE IF EXISTS stg_people, stg_courses, stg_admissions, stg_events,
                     stg_assets, stg_attachments, stg_course_track_map,
                     stg_rag_documents, stg_rag_chunks, stg_quality;

CREATE TABLE stg_people (
    record_id TEXT, dept_name TEXT, dept TEXT, name TEXT, name_ko TEXT, name_en TEXT,
    role TEXT, role_normalized TEXT, faculty_group TEXT, email TEXT, phone TEXT,
    office TEXT, research_area TEXT, homepage TEXT, image_url TEXT,
    source_url TEXT, crawled_at TEXT, missing_fields TEXT
);
CREATE TABLE stg_courses (
    record_id TEXT, dept_name TEXT, dept TEXT, course_level TEXT, course_code TEXT,
    course_name TEXT, course_type TEXT, credit TEXT, course_description TEXT,
    raw_values TEXT, source_url TEXT, crawled_at TEXT, missing_fields TEXT
);
CREATE TABLE stg_admissions (
    record_id TEXT, dept_name TEXT, dept TEXT, admission_type TEXT, page_title TEXT,
    section_title TEXT, title TEXT, content TEXT, schedule_date TEXT,
    source_url TEXT, crawled_at TEXT, source_sheet TEXT, missing_fields TEXT
);
CREATE TABLE stg_events (
    record_id TEXT, dept_name TEXT, dept TEXT, event_type TEXT, page_title TEXT,
    title TEXT, content TEXT, event_date TEXT, source_url TEXT,
    crawled_at TEXT, missing_fields TEXT
);
CREATE TABLE stg_assets (
    record_id TEXT, dept_name TEXT, dept TEXT, category TEXT, topic TEXT, priority TEXT,
    content_type TEXT, asset_type TEXT, text TEXT, url TEXT, filename TEXT,
    source_url TEXT, crawled_at TEXT, missing_fields TEXT
);
CREATE TABLE stg_attachments (
    dept TEXT, board TEXT, post_id TEXT, filename TEXT, url TEXT, ext TEXT, size TEXT,
    content_type TEXT, download_status TEXT, local_path TEXT, text_extraction_status TEXT,
    text_cache_path TEXT, text_preview TEXT, crawled_at TEXT, missing_fields TEXT
);
CREATE TABLE stg_course_track_map (
    dept_name TEXT, dept TEXT, course_code TEXT, course_name TEXT, track_name TEXT,
    course_type TEXT, course_description TEXT, source_url TEXT, record_id TEXT, crawled_at TEXT
);
CREATE TABLE stg_rag_documents (
    doc_id TEXT, dept TEXT, dept_name TEXT, source_type TEXT, title TEXT,
    source_url TEXT, source_board TEXT, crawled_at TEXT, chunk_count TEXT
);
CREATE TABLE stg_rag_chunks (
    chunk_id TEXT, doc_id TEXT, dept TEXT, dept_name TEXT, source_type TEXT, title TEXT,
    section_path TEXT, chunk_text TEXT, source_url TEXT, source_board TEXT,
    source_record_id TEXT, crawled_at TEXT, missing_fields TEXT, metadata_json TEXT
);
CREATE TABLE stg_quality (metric TEXT, value TEXT, note TEXT);


-- =====================================================================
--  STEP 2. CSV → 스테이징 적재 (LOAD DATA LOCAL INFILE)
--  옵션 의미:
--   FIELDS TERMINATED BY ','           열 구분자는 콤마
--   OPTIONALLY ENCLOSED BY '"'          따옴표로 감싼 필드 지원 → 필드 안의 콤마/줄바꿈 보존
--   LINES TERMINATED BY '\r\n'          윈도우 줄끝(CRLF). 따옴표 안의 줄바꿈은 그대로 데이터.
--   IGNORE 1 LINES                      첫 줄(헤더) 건너뜀
--   CHARACTER SET utf8mb4               한글 깨짐 방지
-- =====================================================================
LOAD DATA LOCAL INFILE 'csv/_clean/people_clean.csv'
  INTO TABLE stg_people CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'csv/_clean/courses_clean.csv'
  INTO TABLE stg_courses CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'csv/_clean/admissions_clean.csv'
  INTO TABLE stg_admissions CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'csv/_clean/events_clean.csv'
  INTO TABLE stg_events CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'csv/_clean/assets_clean.csv'
  INTO TABLE stg_assets CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'csv/_clean/attachments_clean.csv'
  INTO TABLE stg_attachments CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'csv/_clean/course_track_map.csv'
  INTO TABLE stg_course_track_map CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'csv/_clean/rag_documents.csv'
  INTO TABLE stg_rag_documents CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'csv/_clean/rag_chunks.csv'
  INTO TABLE stg_rag_chunks CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'csv/_clean/quality_report.csv'
  INTO TABLE stg_quality CHARACTER SET utf8mb4
  FIELDS TERMINATED BY ',' ENCLOSED BY '"'
  LINES TERMINATED BY '\r\n' IGNORE 1 LINES;


-- =====================================================================
--  STEP 3. 정규화 테이블로 변환 적재 (INSERT ... SELECT)
-- =====================================================================

-- 3-1) department : 여러 스테이징에 흩어진 (dept, dept_name) 을 DISTINCT 로 한 번만 추출.
--      UNION 은 자동으로 중복을 제거하므로 학과 4건만 남는다.
INSERT INTO department (dept, dept_name)
SELECT DISTINCT dept, dept_name FROM stg_people
UNION
SELECT DISTINCT dept, dept_name FROM stg_courses
UNION
SELECT DISTINCT dept, dept_name FROM stg_admissions
UNION
SELECT DISTINCT dept, dept_name FROM stg_assets
UNION
SELECT DISTINCT dept, dept_name FROM stg_rag_documents;

-- 3-2) person : dept_name 열만 빼고 그대로 옮긴다. (빈 문자열은 NULL 로 정리)
INSERT IGNORE INTO person
SELECT record_id, dept, name, name_ko, name_en, role, role_normalized, faculty_group,
       NULLIF(email,''), NULLIF(phone,''), NULLIF(office,''), NULLIF(research_area,''),
       NULLIF(homepage,''), NULLIF(image_url,''), source_url, crawled_at, missing_fields
FROM stg_people;

-- 3-3) course
INSERT IGNORE INTO course
SELECT record_id, dept, course_level, course_code, course_name, course_type,
       NULLIF(credit,''), NULLIF(course_description,''), raw_values,
       source_url, crawled_at, missing_fields
FROM stg_courses;

-- 3-4) admission
INSERT IGNORE INTO admission
SELECT record_id, dept, admission_type, page_title, section_title, title, content,
       NULLIF(schedule_date,''), source_url, crawled_at, source_sheet, missing_fields
FROM stg_admissions;

-- 3-5) event
INSERT IGNORE INTO event
SELECT record_id, dept, event_type, page_title, title, content,
       NULLIF(event_date,''), source_url, crawled_at, missing_fields
FROM stg_events;

-- 3-6) asset : 원본 CSV에 중복 record_id 219그룹(224행) 존재 → IGNORE로 첫 번째 행만 보존 (494 → 270행)
INSERT IGNORE INTO asset
SELECT record_id, dept, category, topic, priority, content_type, asset_type, text,
       url, NULLIF(filename,''), source_url, crawled_at, missing_fields
FROM stg_assets;

-- 3-7) attachment : attachment_id 는 AUTO_INCREMENT 라 SELECT 에서 제외(= 자동 채번).
--      size 는 문자열 → 숫자. 빈값이면 NULL.
INSERT INTO attachment
 (dept, board, post_id, filename, url, ext, size, content_type, download_status,
  local_path, text_extraction_status, text_cache_path, text_preview, crawled_at, missing_fields)
SELECT dept, board, post_id, filename, url, ext,
       CAST(NULLIF(size,'') AS UNSIGNED),
       NULLIF(content_type,''), download_status, local_path, text_extraction_status,
       text_cache_path, text_preview, crawled_at, missing_fields
FROM stg_attachments;

-- 3-8) track : 과목-트랙 매핑에서 (학과, 트랙명) 의 고유 목록만 뽑아 마스터를 만든다.
--      track_id 는 AUTO_INCREMENT 로 자동 부여.
INSERT INTO track (dept, track_name)
SELECT DISTINCT dept, track_name
FROM stg_course_track_map
WHERE track_name IS NOT NULL AND track_name <> '';

-- 3-9) course_track : 교차 엔터티 채우기 — 두 마스터에 JOIN 해서 키를 '연결'한다.
--      · course      : 매핑의 record_id 가 실제 과목으로 존재할 때만 (INNER JOIN) → FK 위반 방지
--      · track       : (dept, track_name) 으로 방금 만든 track_id 를 찾아옴
--      DISTINCT 로 (course_id, track_id) 복합키 중복을 사전 차단.
INSERT INTO course_track (course_id, track_id, course_type)
SELECT DISTINCT c.record_id, t.track_id, m.course_type
FROM stg_course_track_map m
JOIN course c ON c.record_id = m.record_id           -- 존재하는 과목만
JOIN track  t ON t.dept = m.dept
             AND t.track_name = m.track_name;

-- 3-10) rag_document
INSERT IGNORE INTO rag_document
SELECT doc_id, dept, source_type, title, NULLIF(source_url,''), NULLIF(source_board,''),
       crawled_at,
       CAST(CAST(NULLIF(chunk_count,'') AS DECIMAL(10,2)) AS UNSIGNED)  -- "1.0" → 1
FROM stg_rag_documents;

-- 3-11) rag_chunk : 문서 메타(dept/source_type/title/source_url/source_board/crawled_at)는
--       rag_document 와 100% 중복(이행적 종속)이라 정규화 정리로 제거됨 → 청크 고유 컬럼만 적재.
--       (스테이징은 CSV 원본 그대로 받되, 여기서 필요한 열만 골라 넣는다)
INSERT IGNORE INTO rag_chunk
 (chunk_id, doc_id, section_path, chunk_text, source_record_id, missing_fields, metadata_json)
SELECT chunk_id, doc_id, section_path, chunk_text,
       NULLIF(source_record_id,''), missing_fields, metadata_json
FROM stg_rag_chunks;

-- 3-12) quality_report : 원본 끝에 붙은 빈 행은 버리고 실제 지표만.
INSERT INTO quality_report (metric, value, note)
SELECT metric, value, note
FROM stg_quality
WHERE metric IS NOT NULL AND metric <> '';


-- =====================================================================
--  STEP 4. 마무리 — FK 검사 다시 켜기. (스테이징은 검증 후 지워도 됨)
-- =====================================================================
SET FOREIGN_KEY_CHECKS = 1;

-- 필요 없으면 아래 주석을 풀어 스테이징 정리:
-- DROP TABLE stg_people, stg_courses, stg_admissions, stg_events, stg_assets,
--            stg_attachments, stg_course_track_map, stg_rag_documents,
--            stg_rag_chunks, stg_quality;
