-- ============================================================
-- 01_schema.sql
-- KAIST AI College RAG Agent MySQL Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS kaist_ai
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_unicode_ci;

USE kaist_ai;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 기존 테이블 삭제
-- ============================================================

DROP TABLE IF EXISTS course_track;
DROP TABLE IF EXISTS track;
DROP TABLE IF EXISTS department_requirement;
DROP TABLE IF EXISTS department_homepage;
DROP TABLE IF EXISTS department_offices;
DROP TABLE IF EXISTS kaist_links;
DROP TABLE IF EXISTS kaist_statistics;
DROP TABLE IF EXISTS kaist_profile;
DROP TABLE IF EXISTS attachment;
DROP TABLE IF EXISTS asset;
DROP TABLE IF EXISTS event;
DROP TABLE IF EXISTS admission;
DROP TABLE IF EXISTS course;
DROP TABLE IF EXISTS person;
DROP TABLE IF EXISTS department;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 1. 학과 기본 테이블
-- ============================================================

CREATE TABLE department (
    dept       VARCHAR(50) NOT NULL,
    dept_name VARCHAR(255) NOT NULL,

    PRIMARY KEY (dept),
    UNIQUE KEY uk_department_name (dept_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 2. 교수진 / 구성원
-- ============================================================

CREATE TABLE person (
    record_id       VARCHAR(255) NOT NULL,
    dept            VARCHAR(50) NULL,
    name            VARCHAR(255) NULL,
    name_ko         VARCHAR(255) NULL,
    name_en         VARCHAR(255) NULL,
    role            VARCHAR(255) NULL,
    role_normalized VARCHAR(255) NULL,
    faculty_group   VARCHAR(255) NULL,
    email           VARCHAR(255) NULL,
    phone           VARCHAR(100) NULL,
    office          VARCHAR(255) NULL,
    research_area   TEXT NULL,
    homepage        VARCHAR(1000) NULL,
    source_url      VARCHAR(1000) NULL,
    crawled_at      VARCHAR(100) NULL,
    source_sheet    VARCHAR(255) NULL,
    missing_fields  TEXT NULL,

    PRIMARY KEY (record_id),
    INDEX idx_person_dept (dept),
    INDEX idx_person_name (name),
    INDEX idx_person_email (email),
    INDEX idx_person_role (role_normalized),
    CONSTRAINT fk_person_dept
        FOREIGN KEY (dept) REFERENCES department(dept)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 3. 교과목
-- ============================================================

CREATE TABLE course (
    record_id          VARCHAR(255) NOT NULL,
    course_id          VARCHAR(255) NULL,
    dept               VARCHAR(50) NULL,
    course_level       VARCHAR(100) NULL,
    course_code        VARCHAR(100) NULL,
    course_code_norm   VARCHAR(100) NULL,
    course_name        VARCHAR(500) NULL,
    course_type        VARCHAR(100) NULL,
    credit             VARCHAR(50) NULL,
    course_description TEXT NULL,
    source_url         VARCHAR(1000) NULL,
    crawled_at         VARCHAR(100) NULL,
    source_sheet       VARCHAR(255) NULL,
    missing_fields     TEXT NULL,

    PRIMARY KEY (record_id),
    INDEX idx_course_dept (dept),
    INDEX idx_course_code (course_code),
    INDEX idx_course_code_norm (course_code_norm),
    INDEX idx_course_name (course_name(255)),
    INDEX idx_course_type (course_type),
    CONSTRAINT fk_course_dept
        FOREIGN KEY (dept) REFERENCES department(dept)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 4. 트랙 / 교과목-트랙 매핑
-- ============================================================

CREATE TABLE track (
    track_id   VARCHAR(255) NOT NULL,
    dept       VARCHAR(50) NULL,
    track_name VARCHAR(500) NOT NULL,

    PRIMARY KEY (track_id),
    INDEX idx_track_dept (dept),
    INDEX idx_track_name (track_name(255)),
    CONSTRAINT fk_track_dept
        FOREIGN KEY (dept) REFERENCES department(dept)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE course_track (
    course_id   VARCHAR(255) NOT NULL,
    track_id    VARCHAR(255) NOT NULL,
    course_type VARCHAR(100) NULL,

    PRIMARY KEY (course_id, track_id),
    INDEX idx_course_track_course_id (course_id),
    INDEX idx_course_track_track_id (track_id),
    CONSTRAINT fk_course_track_course
        FOREIGN KEY (course_id) REFERENCES course(record_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_course_track_track
        FOREIGN KEY (track_id) REFERENCES track(track_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 5. 입학 정보
-- ============================================================

CREATE TABLE admission (
    admission_id        VARCHAR(255) NOT NULL,
    record_id           VARCHAR(255) NULL,
    dept_name           VARCHAR(255) NULL,
    dept                VARCHAR(50) NULL,
    admission_type      VARCHAR(100) NULL,
    admission_type_norm VARCHAR(100) NULL,
    page_title          VARCHAR(500) NULL,
    section_title       VARCHAR(500) NULL,
    title               VARCHAR(500) NULL,
    content             TEXT NULL,
    schedule_date       VARCHAR(50) NULL,
    schedule_date_raw   VARCHAR(100) NULL,
    min_gpa             VARCHAR(50) NULL,
    source_url          VARCHAR(1000) NULL,
    crawled_at          VARCHAR(100) NULL,
    source_sheet        VARCHAR(255) NULL,
    missing_fields      TEXT NULL,

    PRIMARY KEY (admission_id),
    INDEX idx_admission_dept (dept),
    INDEX idx_admission_type (admission_type),
    INDEX idx_admission_type_norm (admission_type_norm),
    INDEX idx_admission_schedule_date (schedule_date),
    CONSTRAINT fk_admission_dept
        FOREIGN KEY (dept) REFERENCES department(dept)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 6. 행사 / 공지
-- ============================================================

CREATE TABLE event (
    record_id      VARCHAR(255) NOT NULL,
    dept           VARCHAR(50) NULL,
    event_type     VARCHAR(100) NULL,
    page_title     VARCHAR(500) NULL,
    title          VARCHAR(500) NULL,
    event_date     VARCHAR(50) NULL,
    summary        TEXT NULL,
    content        TEXT NULL,
    source_url     VARCHAR(1000) NULL,
    crawled_at     VARCHAR(100) NULL,
    missing_fields TEXT NULL,

    PRIMARY KEY (record_id),
    INDEX idx_event_dept (dept),
    INDEX idx_event_type (event_type),
    INDEX idx_event_date (event_date),
    CONSTRAINT fk_event_dept
        FOREIGN KEY (dept) REFERENCES department(dept)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 7. 웹 자산 / 링크 / 연락처
-- ============================================================

CREATE TABLE asset (
    asset_id            VARCHAR(255) NOT NULL,
    record_id           VARCHAR(255) NULL,
    dept                VARCHAR(50) NULL,
    category            VARCHAR(100) NULL,
    topic               VARCHAR(255) NULL,
    priority            VARCHAR(50) NULL,
    content_type        VARCHAR(100) NULL,
    asset_type          VARCHAR(100) NULL,
    text                TEXT NULL,
    url                 VARCHAR(1000) NULL,
    filename            VARCHAR(255) NULL,
    source_url          VARCHAR(1000) NULL,
    crawled_at          VARCHAR(100) NULL,
    missing_fields      TEXT NULL,
    is_vector_candidate VARCHAR(20) NULL,

    PRIMARY KEY (asset_id),
    INDEX idx_asset_record_id (record_id),
    INDEX idx_asset_dept (dept),
    INDEX idx_asset_content_type (content_type),
    INDEX idx_asset_asset_type (asset_type),
    INDEX idx_asset_url (url(255)),
    CONSTRAINT fk_asset_dept
        FOREIGN KEY (dept) REFERENCES department(dept)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 8. 첨부파일 메타데이터
-- ============================================================

CREATE TABLE attachment (
    attachment_id                    VARCHAR(255) NOT NULL,
    record_id                        VARCHAR(255) NULL,
    dept_name                        VARCHAR(255) NULL,
    dept                             VARCHAR(50) NULL,
    board                            VARCHAR(255) NULL,
    filename                         VARCHAR(500) NULL,
    ext                              VARCHAR(50) NULL,
    size                             VARCHAR(100) NULL,
    url                              VARCHAR(1000) NULL,
    source_url                       VARCHAR(1000) NULL,
    text_preview                     TEXT NULL,
    crawled_at                       VARCHAR(100) NULL,
    source_sheet                     VARCHAR(255) NULL,
    missing_fields                   TEXT NULL,
    use_text_preview_for_vectorstore VARCHAR(50) NULL,
    note                             TEXT NULL,

    PRIMARY KEY (attachment_id),
    INDEX idx_attachment_dept (dept),
    INDEX idx_attachment_filename (filename(255)),
    INDEX idx_attachment_ext (ext),
    CONSTRAINT fk_attachment_dept
        FOREIGN KEY (dept) REFERENCES department(dept)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 9. KAIST 학과사무실
-- ============================================================

CREATE TABLE department_offices (
    office_id         VARCHAR(255) NOT NULL,
    program_name     VARCHAR(500) NULL,
    phone            VARCHAR(255) NULL,
    website          VARCHAR(1000) NULL,
    building_location VARCHAR(500) NULL,
    source           VARCHAR(500) NULL,
    source_page      VARCHAR(100) NULL,
    missing_fields   TEXT NULL,

    PRIMARY KEY (office_id),
    INDEX idx_department_offices_program (program_name(255)),
    INDEX idx_department_offices_phone (phone),
    INDEX idx_department_offices_website (website(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 10. KAIST 기본정보 / 통계 / 공식 링크
-- ============================================================

CREATE TABLE kaist_profile (
    item       VARCHAR(255) NULL,
    content    TEXT NULL,
    note       TEXT NULL,
    source_url VARCHAR(1000) NULL,
    source     VARCHAR(255) NULL,

    INDEX idx_kaist_profile_item (item)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE kaist_statistics (
    stat_group   VARCHAR(100) NULL,
    level        VARCHAR(100) NULL,
    value_raw    VARCHAR(100) NULL,
    value_number VARCHAR(100) NULL,
    note         TEXT NULL,
    source       VARCHAR(255) NULL,

    INDEX idx_kaist_statistics_group (stat_group),
    INDEX idx_kaist_statistics_level (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE kaist_links (
    link_name VARCHAR(255) NULL,
    url       VARCHAR(1000) NULL,
    note      TEXT NULL,
    source    VARCHAR(255) NULL,

    INDEX idx_kaist_links_name (link_name),
    INDEX idx_kaist_links_url (url(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 11. 학과별 대표 홈페이지
-- ============================================================

CREATE TABLE department_homepage (
    dept           VARCHAR(50) NOT NULL,
    dept_name      VARCHAR(255) NOT NULL,
    homepage_url   VARCHAR(1000) NULL,
    admission_url  VARCHAR(1000) NULL,
    faculty_url    VARCHAR(1000) NULL,
    curriculum_url VARCHAR(1000) NULL,
    source         VARCHAR(255) NULL,

    PRIMARY KEY (dept),
    INDEX idx_department_homepage_name (dept_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 12. 학과별 졸업/수료/논문/이수 요건
-- 현재 데이터가 없더라도 빈 테이블로 둔다.
-- ============================================================

CREATE TABLE department_requirement (
    requirement_id   VARCHAR(255) NOT NULL,
    dept             VARCHAR(50) NULL,
    dept_name        VARCHAR(255) NULL,
    program          VARCHAR(100) NULL,
    requirement_type VARCHAR(100) NULL,
    requirement_name VARCHAR(255) NULL,
    description      TEXT NULL,
    credits          VARCHAR(50) NULL,
    source_url       VARCHAR(1000) NULL,
    note             TEXT NULL,

    PRIMARY KEY (requirement_id),
    INDEX idx_requirement_dept (dept),
    INDEX idx_requirement_type (requirement_type),
    INDEX idx_requirement_program (program),
    CONSTRAINT fk_requirement_dept
        FOREIGN KEY (dept) REFERENCES department(dept)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;