-- ============================================================
-- 02_load.sql
-- KAIST AI College RAG Agent CSV Load Script
-- ============================================================

USE kaist_ai;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 0. 기존 데이터 초기화
-- ============================================================

TRUNCATE TABLE course_track;
TRUNCATE TABLE track;
TRUNCATE TABLE department_requirement;
TRUNCATE TABLE department_homepage;
TRUNCATE TABLE department_offices;
TRUNCATE TABLE kaist_links;
TRUNCATE TABLE kaist_statistics;
TRUNCATE TABLE kaist_profile;
TRUNCATE TABLE attachment;
TRUNCATE TABLE asset;
TRUNCATE TABLE event;
TRUNCATE TABLE admission;
TRUNCATE TABLE course;
TRUNCATE TABLE person;
TRUNCATE TABLE department;

-- ============================================================
-- 1. staging 테이블 생성
-- ============================================================

DROP TABLE IF EXISTS stg_admissions;
CREATE TABLE stg_admissions (
    record_id           TEXT,
    dept_name           TEXT,
    dept                TEXT,
    admission_type      TEXT,
    page_title          TEXT,
    section_title       TEXT,
    title               TEXT,
    content             TEXT,
    schedule_date       TEXT,
    source_url          TEXT,
    crawled_at          TEXT,
    source_sheet        TEXT,
    missing_fields      TEXT,
    admission_type_norm TEXT,
    schedule_date_raw   TEXT,
    min_gpa             TEXT,
    admission_id        TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_courses;
CREATE TABLE stg_courses (
    record_id          TEXT,
    dept_name          TEXT,
    dept               TEXT,
    course_level       TEXT,
    course_code        TEXT,
    course_name        TEXT,
    course_type        TEXT,
    credit             TEXT,
    course_description TEXT,
    source_url         TEXT,
    crawled_at         TEXT,
    source_sheet       TEXT,
    missing_fields     TEXT,
    course_code_norm   TEXT,
    course_id          TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_course_track_map;
CREATE TABLE stg_course_track_map (
    record_id          TEXT,
    dept_name          TEXT,
    dept               TEXT,
    track_name         TEXT,
    course_code        TEXT,
    course_name        TEXT,
    course_type        TEXT,
    course_description TEXT,
    source_url         TEXT,
    crawled_at         TEXT,
    course_code_norm   TEXT,
    course_track_id    TEXT,
    missing_fields     TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_people;
CREATE TABLE stg_people (
    record_id       TEXT,
    dept_name       TEXT,
    dept            TEXT,
    name            TEXT,
    name_ko         TEXT,
    name_en         TEXT,
    role            TEXT,
    role_normalized TEXT,
    faculty_group   TEXT,
    email           TEXT,
    phone           TEXT,
    office          TEXT,
    research_area   TEXT,
    homepage        TEXT,
    source_url      TEXT,
    crawled_at      TEXT,
    source_sheet    TEXT,
    missing_fields  TEXT,
    person_id       TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_events;
CREATE TABLE stg_events (
    record_id      TEXT,
    dept_name      TEXT,
    dept           TEXT,
    event_type     TEXT,
    page_title     TEXT,
    title          TEXT,
    event_date     TEXT,
    summary        TEXT,
    content        TEXT,
    source_url     TEXT,
    crawled_at     TEXT,
    missing_fields TEXT,
    event_id       TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_assets;
CREATE TABLE stg_assets (
    record_id           TEXT,
    dept_name           TEXT,
    dept                TEXT,
    category            TEXT,
    topic               TEXT,
    priority            TEXT,
    content_type        TEXT,
    asset_type          TEXT,
    text                TEXT,
    url                 TEXT,
    filename            TEXT,
    source_url          TEXT,
    crawled_at          TEXT,
    missing_fields      TEXT,
    asset_id            TEXT,
    is_vector_candidate TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_attachments;
CREATE TABLE stg_attachments (
    record_id                        TEXT,
    dept_name                        TEXT,
    dept                             TEXT,
    board                            TEXT,
    filename                         TEXT,
    ext                              TEXT,
    size                             TEXT,
    url                              TEXT,
    source_url                       TEXT,
    text_preview                     TEXT,
    crawled_at                       TEXT,
    source_sheet                     TEXT,
    missing_fields                   TEXT,
    attachment_id                    TEXT,
    use_text_preview_for_vectorstore TEXT,
    note                             TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_department_offices;
CREATE TABLE stg_department_offices (
    program_name      TEXT,
    phone             TEXT,
    website           TEXT,
    building_location TEXT,
    office_id         TEXT,
    source            TEXT,
    source_page       TEXT,
    missing_fields    TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_kaist_profile;
CREATE TABLE stg_kaist_profile (
    item       TEXT,
    content    TEXT,
    note       TEXT,
    source_url TEXT,
    source     TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_kaist_statistics;
CREATE TABLE stg_kaist_statistics (
    stat_group   TEXT,
    level        TEXT,
    value_raw    TEXT,
    value_number TEXT,
    note         TEXT,
    source       TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


DROP TABLE IF EXISTS stg_kaist_links;
CREATE TABLE stg_kaist_links (
    link_name TEXT,
    url       TEXT,
    note      TEXT,
    source    TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 2. CSV → staging 적재
-- 경로가 다르면 C:/Users/Playdata/workspace/SKN28-third-2TEAM 부분만 수정
-- ============================================================

LOAD DATA LOCAL INFILE 'data/processed/csv/admissions.csv'
INTO TABLE stg_admissions
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(record_id, dept_name, dept, admission_type, page_title, section_title, title, content,
 schedule_date, source_url, crawled_at, source_sheet, missing_fields,
 admission_type_norm, schedule_date_raw, min_gpa, admission_id);


LOAD DATA LOCAL INFILE 'data/processed/csv/courses.csv'
INTO TABLE stg_courses
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(record_id, dept_name, dept, course_level, course_code, course_name, course_type,
 credit, course_description, @raw_values, source_url, crawled_at, missing_fields,
 course_code_norm, course_id);


LOAD DATA LOCAL INFILE 'data/processed/csv/course_track_map.csv'
INTO TABLE stg_course_track_map
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(dept_name, dept, course_code, course_name, track_name, course_type,
 course_description, source_url, record_id, crawled_at, course_code_norm,
 course_track_id, missing_fields);


LOAD DATA LOCAL INFILE 'data/processed/csv/people.csv'
INTO TABLE stg_people
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(record_id, dept_name, dept, name, name_ko, name_en, role, role_normalized,
 faculty_group, email, phone, office, research_area, homepage, @image_url,
 source_url, crawled_at, missing_fields, person_id);


LOAD DATA LOCAL INFILE 'data/processed/csv/events.csv'
INTO TABLE stg_events
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(record_id, dept_name, dept, event_type, page_title, title, content,
 event_date, source_url, crawled_at, missing_fields, event_id);


LOAD DATA LOCAL INFILE 'data/processed/csv/assets.csv'
INTO TABLE stg_assets
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(record_id, dept_name, dept, category, topic, priority, content_type, asset_type,
 text, url, filename, source_url, crawled_at, missing_fields, asset_id,
 is_vector_candidate);


LOAD DATA LOCAL INFILE 'data/processed/csv/attachments.csv'
INTO TABLE stg_attachments
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(@dept, @board, @post_id, filename, url, ext, size, @content_type,
 @download_status, @local_path, @text_extraction_status, @text_cache_path,
 text_preview, crawled_at, missing_fields, attachment_id,
 use_text_preview_for_vectorstore, note)
SET
    dept = @dept,
    board = @board,
    record_id = @post_id,
    source_url = url;


LOAD DATA LOCAL INFILE 'data/processed/csv/department_offices.csv'
INTO TABLE stg_department_offices
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(program_name, phone, website, building_location, office_id, source, source_page, missing_fields);


LOAD DATA LOCAL INFILE 'data/processed/csv/kaist_profile.csv'
INTO TABLE stg_kaist_profile
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(item, content, note, source_url, source);


LOAD DATA LOCAL INFILE 'data/processed/csv/kaist_statistics.csv'
INTO TABLE stg_kaist_statistics
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(stat_group, level, value_raw, value_number, note, source);


LOAD DATA LOCAL INFILE 'data/processed/csv/kaist_links.csv'
INTO TABLE stg_kaist_links
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(link_name, url, note, source);


-- ============================================================
-- 3. department 적재
-- ============================================================

INSERT IGNORE INTO department (dept, dept_name)
SELECT DISTINCT dept, dept_name
FROM stg_people
WHERE dept IS NOT NULL AND dept <> ''

UNION

SELECT DISTINCT dept, dept_name
FROM stg_courses
WHERE dept IS NOT NULL AND dept <> ''

UNION

SELECT DISTINCT dept, dept_name
FROM stg_admissions
WHERE dept IS NOT NULL AND dept <> ''

UNION

SELECT DISTINCT dept, dept_name
FROM stg_assets
WHERE dept IS NOT NULL AND dept <> ''

UNION

SELECT DISTINCT dept, dept_name
FROM stg_events
WHERE dept IS NOT NULL AND dept <> '';


-- ============================================================
-- 4. 본 테이블 적재
-- ============================================================

INSERT IGNORE INTO admission (
    admission_id, record_id, dept_name, dept, admission_type, admission_type_norm,
    page_title, section_title, title, content, schedule_date, schedule_date_raw,
    min_gpa, source_url, crawled_at, source_sheet, missing_fields
)
SELECT
    COALESCE(NULLIF(admission_id, ''), MD5(CONCAT_WS('|', dept, admission_type, title, content))),
    record_id,
    dept_name,
    dept,
    admission_type,
    admission_type_norm,
    page_title,
    section_title,
    title,
    content,
    schedule_date,
    schedule_date_raw,
    min_gpa,
    source_url,
    crawled_at,
    source_sheet,
    missing_fields
FROM stg_admissions;


INSERT IGNORE INTO course (
    record_id, course_id, dept, course_level, course_code, course_code_norm,
    course_name, course_type, credit, course_description,
    source_url, crawled_at, source_sheet, missing_fields
)
SELECT
    record_id,
    course_id,
    dept,
    course_level,
    course_code,
    course_code_norm,
    course_name,
    course_type,
    credit,
    course_description,
    source_url,
    crawled_at,
    source_sheet,
    missing_fields
FROM stg_courses;


INSERT IGNORE INTO person (
    record_id, dept, name, name_ko, name_en, role, role_normalized,
    faculty_group, email, phone, office, research_area, homepage,
    source_url, crawled_at, source_sheet, missing_fields
)
SELECT
    COALESCE(NULLIF(person_id, ''), record_id),
    dept,
    name,
    name_ko,
    name_en,
    role,
    role_normalized,
    faculty_group,
    email,
    phone,
    office,
    research_area,
    homepage,
    source_url,
    crawled_at,
    source_sheet,
    missing_fields
FROM stg_people;


INSERT IGNORE INTO event (
    record_id, dept, event_type, page_title, title, event_date,
    summary, content, source_url, crawled_at, missing_fields
)
SELECT
    COALESCE(NULLIF(event_id, ''), record_id),
    dept,
    event_type,
    page_title,
    title,
    event_date,
    summary,
    content,
    source_url,
    crawled_at,
    missing_fields
FROM stg_events;


INSERT IGNORE INTO asset (
    asset_id, record_id, dept, category, topic, priority, content_type,
    asset_type, text, url, filename, source_url, crawled_at,
    missing_fields, is_vector_candidate
)
SELECT
    COALESCE(NULLIF(asset_id, ''), MD5(CONCAT_WS('|', dept, source_url, url, content_type, text))),
    record_id,
    dept,
    category,
    topic,
    priority,
    content_type,
    asset_type,
    text,
    url,
    filename,
    source_url,
    crawled_at,
    missing_fields,
    is_vector_candidate
FROM stg_assets;


INSERT IGNORE INTO attachment (
    attachment_id, record_id, dept_name, dept, board, filename, ext,
    size, url, source_url, text_preview, crawled_at, source_sheet,
    missing_fields, use_text_preview_for_vectorstore, note
)
SELECT
    COALESCE(NULLIF(attachment_id, ''), MD5(CONCAT_WS('|', dept, filename, url))),
    record_id,
    dept_name,
    dept,
    board,
    filename,
    ext,
    size,
    url,
    source_url,
    text_preview,
    crawled_at,
    source_sheet,
    missing_fields,
    use_text_preview_for_vectorstore,
    note
FROM stg_attachments;


INSERT IGNORE INTO department_offices (
    office_id, program_name, phone, website, building_location,
    source, source_page, missing_fields
)
SELECT
    MD5(CONCAT_WS('|', program_name, phone, website, building_location)) AS office_id,
    program_name,
    phone,
    website,
    building_location,
    source,
    source_page,
    missing_fields
FROM stg_department_offices
WHERE program_name IS NOT NULL
  AND program_name <> ''
  AND program_name <> '학과/프로그램';


-- ============================================================
-- 5. track / course_track 적재
-- ============================================================

INSERT IGNORE INTO track (track_id, dept, track_name)
SELECT
    MD5(CONCAT_WS('|', dept, track_name)) AS track_id,
    dept,
    track_name
FROM stg_course_track_map
WHERE track_name IS NOT NULL
  AND track_name <> ''
  AND dept IS NOT NULL
  AND dept <> '';


INSERT IGNORE INTO course_track (course_id, track_id, course_type)
SELECT DISTINCT
    c.record_id AS course_id,
    t.track_id,
    m.course_type
FROM stg_course_track_map AS m
JOIN course AS c
  ON c.dept = m.dept
 AND (
        (c.course_code_norm IS NOT NULL AND c.course_code_norm <> '' AND c.course_code_norm = m.course_code_norm)
        OR
        (c.course_code IS NOT NULL AND c.course_code <> '' AND c.course_code = m.course_code)
     )
 AND c.course_name = m.course_name
JOIN track AS t
  ON t.dept = m.dept
 AND t.track_name = m.track_name
WHERE m.track_name IS NOT NULL
  AND m.track_name <> '';


-- ============================================================
-- 6. KAIST 기본정보 / 통계 / 링크 적재
-- ============================================================

INSERT INTO kaist_profile (item, content, note, source_url, source)
SELECT item, content, note, source_url, source
FROM stg_kaist_profile;


INSERT INTO kaist_statistics (stat_group, level, value_raw, value_number, note, source)
SELECT stat_group, level, value_raw, value_number, note, source
FROM stg_kaist_statistics;


INSERT INTO kaist_links (link_name, url, note, source)
SELECT link_name, url, note, source
FROM stg_kaist_links;


-- ============================================================
-- 7. 학과별 대표 홈페이지 seed
-- ============================================================

INSERT INTO department_homepage
(dept, dept_name, homepage_url, admission_url, faculty_url, curriculum_url, source)
SELECT
    d.dept,
    d.dept_name,
    CASE d.dept
        WHEN 'aic' THEN 'https://aic.kaist.ac.kr/'
        WHEN 'ai_systems' THEN 'https://ai-systems.kaist.ac.kr/'
        WHEN 'ax' THEN 'https://ax.kaist.ac.kr/'
        WHEN 'fx' THEN 'https://fx.kaist.ac.kr/'
    END AS homepage_url,
    NULL AS admission_url,
    NULL AS faculty_url,
    NULL AS curriculum_url,
    'manual_seed' AS source
FROM department AS d
WHERE d.dept IN ('aic', 'ai_systems', 'ax', 'fx');


SET FOREIGN_KEY_CHECKS = 1;


-- ============================================================
-- 8. 검증
-- ============================================================

SELECT 'department' AS table_name, COUNT(*) AS row_count FROM department
UNION ALL
SELECT 'admission', COUNT(*) FROM admission
UNION ALL
SELECT 'course', COUNT(*) FROM course
UNION ALL
SELECT 'track', COUNT(*) FROM track
UNION ALL
SELECT 'course_track', COUNT(*) FROM course_track
UNION ALL
SELECT 'person', COUNT(*) FROM person
UNION ALL
SELECT 'event', COUNT(*) FROM event
UNION ALL
SELECT 'asset', COUNT(*) FROM asset
UNION ALL
SELECT 'attachment', COUNT(*) FROM attachment
UNION ALL
SELECT 'department_offices', COUNT(*) FROM department_offices
UNION ALL
SELECT 'kaist_profile', COUNT(*) FROM kaist_profile
UNION ALL
SELECT 'kaist_statistics', COUNT(*) FROM kaist_statistics
UNION ALL
SELECT 'kaist_links', COUNT(*) FROM kaist_links
UNION ALL
SELECT 'department_homepage', COUNT(*) FROM department_homepage
UNION ALL
SELECT 'department_requirement', COUNT(*) FROM department_requirement;


SELECT dept, COUNT(*) AS course_count
FROM course
GROUP BY dept
ORDER BY dept;


SELECT dept, COUNT(*) AS person_count
FROM person
GROUP BY dept
ORDER BY dept;


SELECT content_type, COUNT(*) AS asset_count
FROM asset
GROUP BY content_type
ORDER BY asset_count DESC;


SELECT *
FROM department_homepage
ORDER BY FIELD(dept, 'aic', 'ai_systems', 'ax', 'fx');