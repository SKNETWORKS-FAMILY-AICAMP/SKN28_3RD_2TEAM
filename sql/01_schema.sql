-- =====================================================================
--  KAIST AI대학 데이터  관계형 스키마 (MySQL 8.x)
--  설계: 정규화 + PK/FK
--  생성 순서가 곧 의존 순서다 (부모 테이블 먼저, 자식 나중)
--
--  각 컬럼의 COMMENT '...' = 논리명(한국어).
--  ERDCloud 등에서 이 DDL을 import 하면 COMMENT가 '논리명'으로 매핑된다.
--
--  ── 키 전략 (PK/FK 통일 원칙) ───────────────────────────────────────
--   1) 자연키 우선: 크롤링이 제공한 고유 ID가 있으면 그것을 PK로 쓴다.
--                  (person/course/admission/event/asset=record_id,
--                   rag_document=doc_id, rag_chunk=chunk_id)  타입: VARCHAR
--   2) 인조키 예외: 원본에 고유 ID가 없는 '파생 엔터티'만 대리키를 부여한다.
--                  (track, attachment) 타입: BIGINT AUTO_INCREMENT 로 통일.
--                  이때 업무 고유성은 반드시 UNIQUE 제약으로 보장한다.
--   3) dept(VARCHAR(20)) 는 학과 코드라는 '의미 있는 자연 코드키'다.
--  ─────────────────────────────────────────────────────────────────
--
--  ── 주제 영역(subject area) 구분 ────────────────────────────────────
--   · 업무 도메인 : department, person, course, track, course_track,
--                   admission, event
--   · 수집/자원   : asset, attachment   (크롤링 산출물)
--   · RAG 검색    : rag_document, rag_chunk
--   · 독립        : quality_report
--  ─────────────────────────────────────────────────────────────────
-- =====================================================================

-- 1) 데이터베이스 생성 ----------------------------------------------------
--    utf8mb4 = 한글/이모지까지 안전하게 담는 문자셋.
--    (예전 utf8 은 3바이트라 일부 문자가 깨진다)
CREATE DATABASE IF NOT EXISTS kaist_ai
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE kaist_ai;

-- 2) 재실행 대비: 기존 테이블 제거 ----------------------------------------
--    FK 로 묶여 있으면 '자식 → 부모' 순서로 지워야 한다.
--    (부모를 먼저 지우려 하면 FK 위반 에러)
DROP TABLE IF EXISTS rag_chunk;
DROP TABLE IF EXISTS rag_document;
DROP TABLE IF EXISTS course_track;
DROP TABLE IF EXISTS track;
DROP TABLE IF EXISTS attachment;
DROP TABLE IF EXISTS asset;
DROP TABLE IF EXISTS event;
DROP TABLE IF EXISTS admission;
DROP TABLE IF EXISTS course;
DROP TABLE IF EXISTS person;
DROP TABLE IF EXISTS quality_report;
DROP TABLE IF EXISTS department;


-- =====================================================================
--  마스터 엔터티
-- =====================================================================

-- 학과 : 모든 테이블이 참조하는 부모. dept_name 중복을 여기로 모았다 (3NF).
CREATE TABLE department (
    dept       VARCHAR(20)  NOT NULL                COMMENT '학과 코드 (aic/ax/ai_systems/fx)',
    dept_name  VARCHAR(100) NOT NULL                COMMENT '학과명 (한글)',
    CONSTRAINT pk_department PRIMARY KEY (dept)
) ENGINE=InnoDB COMMENT='학과 (마스터)';
--  ENGINE=InnoDB 인 이유: FK(외래키) 제약을 실제로 지켜주는 엔진.
--  MyISAM 으로 만들면 FK 문법은 통과해도 무시된다 → SQLD 함정 포인트.


-- =====================================================================
--  학과에 1:N 으로 매달리는 엔터티들
--  (record_id 라는 '이미 유일한 값'을 자연키 PK로 그대로 사용)
-- =====================================================================

-- 교수 / 구성원
CREATE TABLE person (
    record_id       VARCHAR(255) NOT NULL           COMMENT '레코드 ID',
    dept            VARCHAR(20)  NOT NULL           COMMENT '학과 코드 (FK)',
    name            VARCHAR(100)                    COMMENT '이름',
    name_ko         VARCHAR(100)                    COMMENT '한글 이름',
    name_en         VARCHAR(100)                    COMMENT '영문 이름',
    role            VARCHAR(100)                    COMMENT '직책 (원본)',
    role_normalized VARCHAR(100)                    COMMENT '직책 (정규화)',
    faculty_group   VARCHAR(100)                    COMMENT '교원 구분',
    email           VARCHAR(255)                    COMMENT '이메일',
    phone           VARCHAR(50)                     COMMENT '전화번호',
    office          VARCHAR(255)                    COMMENT '연구실',
    research_area   TEXT                            COMMENT '연구분야',
    homepage        VARCHAR(500)                    COMMENT '홈페이지 URL',
    image_url       VARCHAR(500)                    COMMENT '사진 URL',
    source_url      VARCHAR(500)                    COMMENT '출처 URL',
    crawled_at      VARCHAR(40)                     COMMENT '수집 시각 (ISO8601 문자열)',
    missing_fields  VARCHAR(255)                    COMMENT '누락 필드 목록',
    CONSTRAINT pk_person PRIMARY KEY (record_id),
    CONSTRAINT fk_person_dept FOREIGN KEY (dept)
        REFERENCES department (dept)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='교수/구성원';
--  ON UPDATE CASCADE : 부모 dept 코드가 바뀌면 자식도 따라 바뀜
--  ON DELETE RESTRICT: 자식이 남아있으면 부모 학과 삭제를 막음 (참조 무결성)

-- 교과목
CREATE TABLE course (
    record_id          VARCHAR(255) NOT NULL        COMMENT '레코드 ID',
    dept               VARCHAR(20)  NOT NULL        COMMENT '학과 코드 (FK)',
    course_level       VARCHAR(50)                  COMMENT '과목 레벨',
    course_code        VARCHAR(50)                  COMMENT '과목 코드',
    course_name        VARCHAR(255)                 COMMENT '과목명',
    course_type        VARCHAR(50)                  COMMENT '이수구분',
    credit             VARCHAR(20)                  COMMENT '학점 (비정형 → 문자열)',
    course_description TEXT                         COMMENT '과목 설명',
    raw_values         TEXT                         COMMENT '원본 값 (가공 전)',
    source_url         VARCHAR(500)                 COMMENT '출처 URL',
    crawled_at         VARCHAR(40)                  COMMENT '수집 시각',
    missing_fields     VARCHAR(255)                 COMMENT '누락 필드 목록',
    CONSTRAINT pk_course PRIMARY KEY (record_id),
    CONSTRAINT fk_course_dept FOREIGN KEY (dept)
        REFERENCES department (dept)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_course_code (course_code)          -- 과목코드 조회용 보조 인덱스
) ENGINE=InnoDB COMMENT='교과목';

-- 입학 정보
CREATE TABLE admission (
    record_id       VARCHAR(255) NOT NULL           COMMENT '레코드 ID',
    dept            VARCHAR(20)  NOT NULL           COMMENT '학과 코드 (FK)',
    admission_type  VARCHAR(50)                     COMMENT '입학 유형',
    page_title      VARCHAR(255)                    COMMENT '페이지 제목',
    section_title   VARCHAR(255)                    COMMENT '섹션 제목',
    title           VARCHAR(255)                    COMMENT '제목',
    content         TEXT                            COMMENT '내용',
    schedule_date   VARCHAR(40)                     COMMENT '일정 날짜',
    source_url      VARCHAR(500)                    COMMENT '출처 URL',
    crawled_at      VARCHAR(40)                     COMMENT '수집 시각',
    source_sheet    VARCHAR(50)                     COMMENT '원본 시트명',
    missing_fields  VARCHAR(255)                    COMMENT '누락 필드 목록',
    CONSTRAINT pk_admission PRIMARY KEY (record_id),
    CONSTRAINT fk_admission_dept FOREIGN KEY (dept)
        REFERENCES department (dept)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='입학 정보';

-- 행사
CREATE TABLE event (
    record_id       VARCHAR(255) NOT NULL           COMMENT '레코드 ID',
    dept            VARCHAR(20)  NOT NULL           COMMENT '학과 코드 (FK)',
    event_type      VARCHAR(50)                     COMMENT '행사 유형',
    page_title      VARCHAR(255)                    COMMENT '페이지 제목',
    title           VARCHAR(255)                    COMMENT '제목',
    content         TEXT                            COMMENT '내용',
    event_date      VARCHAR(40)                     COMMENT '행사 날짜',
    source_url      VARCHAR(500)                    COMMENT '출처 URL',
    crawled_at      VARCHAR(40)                     COMMENT '수집 시각',
    missing_fields  VARCHAR(255)                    COMMENT '누락 필드 목록',
    CONSTRAINT pk_event PRIMARY KEY (record_id),
    CONSTRAINT fk_event_dept FOREIGN KEY (dept)
        REFERENCES department (dept)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='행사';

-- 자원 (이미지/링크/이메일/전화 등)
CREATE TABLE asset (
    record_id       VARCHAR(255) NOT NULL           COMMENT '레코드 ID',
    dept            VARCHAR(20)  NOT NULL           COMMENT '학과 코드 (FK)',
    category        VARCHAR(100)                    COMMENT '카테고리',
    topic           VARCHAR(255)                    COMMENT '주제',
    priority        VARCHAR(50)                     COMMENT '우선순위',
    content_type    VARCHAR(50)                     COMMENT '콘텐츠 유형',
    asset_type      VARCHAR(50)                     COMMENT '자원 유형 (image/external/email/phone)',
    text            TEXT                            COMMENT '텍스트',
    url             VARCHAR(1000)                   COMMENT 'URL',
    filename        VARCHAR(255)                    COMMENT '파일명',
    source_url      VARCHAR(500)                    COMMENT '출처 URL',
    crawled_at      VARCHAR(40)                     COMMENT '수집 시각',
    missing_fields  VARCHAR(255)                    COMMENT '누락 필드 목록',
    CONSTRAINT pk_asset PRIMARY KEY (record_id),
    CONSTRAINT fk_asset_dept FOREIGN KEY (dept)
        REFERENCES department (dept)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='자원 (링크/이미지/연락처)';

-- 첨부파일(PDF) : 원본에 record_id 가 없다 → 인조키(AUTO_INCREMENT) 부여
--  [참조 대상 설명] 이 PDF의 '진짜 부모'는 학과가 아니라 게시글(post)이다.
--   (dept, board, post_id) 조합이 출처 게시글을 가리키며, board 값에 따라
--   그 게시글은 admission(입학 안내) 또는 event(공지) 로 실체화된다.
--   다만 post_id 는 admission/event 의 record_id '일부'(부분 문자열)일 뿐
--   완전한 키가 아니라 단일 FK 로 강제할 수 없다 → dept 만 FK 로 두고,
--   게시글 출처는 (dept,board,post_id) UNIQUE 로 식별 + 본 주석으로 명시한다.
CREATE TABLE attachment (
    attachment_id          BIGINT       NOT NULL AUTO_INCREMENT  COMMENT '첨부 ID (대리키)',
    dept                   VARCHAR(20)  NOT NULL    COMMENT '학과 코드 (FK)',
    board                  VARCHAR(100)             COMMENT '게시판 (출처 게시글 구분: admission_* → 입학, site_page/news → 행사)',
    post_id                VARCHAR(100)             COMMENT '게시글 ID (admission/event record_id 의 부분 식별자)',
    filename               VARCHAR(255)             COMMENT '파일명',
    url                    VARCHAR(1000)            COMMENT 'URL',
    ext                    VARCHAR(20)              COMMENT '확장자',
    size                   BIGINT                   COMMENT '파일 크기 (바이트)',
    content_type           VARCHAR(100)             COMMENT '콘텐츠 타입',
    download_status        VARCHAR(50)              COMMENT '다운로드 상태',
    local_path             VARCHAR(1000)            COMMENT '로컬 경로',
    text_extraction_status VARCHAR(50)              COMMENT '텍스트 추출 상태',
    text_cache_path        VARCHAR(1000)            COMMENT '텍스트 캐시 경로',
    text_preview           TEXT                     COMMENT '텍스트 미리보기',
    crawled_at             VARCHAR(40)              COMMENT '수집 시각',
    missing_fields         VARCHAR(255)             COMMENT '누락 필드 목록',
    CONSTRAINT pk_attachment PRIMARY KEY (attachment_id),
    CONSTRAINT uq_attachment UNIQUE (dept, board, post_id, filename),  -- 인조키지만 업무 고유성 보장 (키 전략 원칙 2)
    CONSTRAINT fk_attachment_dept FOREIGN KEY (dept)
        REFERENCES department (dept)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='첨부파일 (PDF) — 부모는 게시글(post), board로 admission/event 구분';


-- =====================================================================
--  M:N 관계 해소 : course ↔ track
-- =====================================================================

-- 트랙/분야 마스터 : 원본엔 이름만 있어 인조키 부여 + (학과,이름) 유일 보장
CREATE TABLE track (
    track_id   BIGINT       NOT NULL AUTO_INCREMENT COMMENT '트랙 ID (대리키)',
    dept       VARCHAR(20)  NOT NULL                COMMENT '학과 코드 (FK)',
    track_name VARCHAR(255) NOT NULL                COMMENT '트랙명',
    CONSTRAINT pk_track PRIMARY KEY (track_id),
    CONSTRAINT uq_track UNIQUE (dept, track_name),   -- 같은 학과 내 트랙명 중복 방지
    CONSTRAINT fk_track_dept FOREIGN KEY (dept)
        REFERENCES department (dept)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='트랙/분야 (마스터)';

-- 교차 엔터티 : '과목 1건 - 트랙 1건' 연결을 한 행으로 저장
CREATE TABLE course_track (
    course_id  VARCHAR(255) NOT NULL                COMMENT '과목 ID (FK)',
    track_id   BIGINT       NOT NULL                COMMENT '트랙 ID (FK)',
    course_type VARCHAR(50)                         COMMENT '이수구분 (해당 트랙에서)',
    CONSTRAINT pk_course_track PRIMARY KEY (course_id, track_id),  -- 복합 기본키
    CONSTRAINT fk_ct_course FOREIGN KEY (course_id)
        REFERENCES course (record_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_ct_track FOREIGN KEY (track_id)
        REFERENCES track (track_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='과목-트랙 교차 엔터티';
--  여기 ON DELETE CASCADE : 과목이나 트랙이 사라지면 그 연결행도 같이 삭제.
--  연결행은 독립적 의미가 없으니 CASCADE 가 자연스럽다.


-- =====================================================================
--  RAG 검색용 텍스트 (문서 1 : 청크 N)
--  문서 메타는 rag_document 에 한 번만 두고, rag_chunk 는 청크 고유 컬럼만 (3NF).
-- =====================================================================

-- 문서 단위 메타데이터
CREATE TABLE rag_document (
    doc_id       VARCHAR(255) NOT NULL              COMMENT '문서 ID',
    dept         VARCHAR(20)  NOT NULL              COMMENT '학과 코드 (FK)',
    source_type  VARCHAR(50)                        COMMENT '출처 유형',
    title        VARCHAR(500)                       COMMENT '제목',
    source_url   VARCHAR(500)                       COMMENT '출처 URL',
    source_board VARCHAR(100)                       COMMENT '출처 게시판',
    crawled_at   VARCHAR(40)                        COMMENT '수집 시각',
    chunk_count  INT                                COMMENT '청크 수',
    CONSTRAINT pk_rag_document PRIMARY KEY (doc_id),
    CONSTRAINT fk_ragdoc_dept FOREIGN KEY (dept)
        REFERENCES department (dept)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB COMMENT='RAG 문서 메타데이터';

-- 청크(임베딩 후보 텍스트 조각) : 문서 1 : 청크 N
--  [정규화 정리] dept/source_type/title/source_url/source_board/crawled_at 는
--   doc_id 에만 종속(이행적 종속)되어 rag_document 와 100% 중복이었다(523행 검증).
--   → 3NF 위반이라 제거. 필요 시 doc_id 로 rag_document 를 JOIN 해서 얻는다.
--   남긴 컬럼은 '청크 고유' 속성뿐이다.
CREATE TABLE rag_chunk (
    chunk_id         VARCHAR(255) NOT NULL          COMMENT '청크 ID',
    doc_id           VARCHAR(255) NOT NULL          COMMENT '문서 ID (FK → rag_document)',
    section_path     VARCHAR(500)                   COMMENT '섹션 경로',
    chunk_text       TEXT                           COMMENT '청크 텍스트',
    source_record_id VARCHAR(255)                   COMMENT '원본 레코드 ID (다형/비정형 출처추적: record_id·URL·자유텍스트 혼재 → FK 미설정)',
    missing_fields   VARCHAR(255)                   COMMENT '누락 필드 목록',
    metadata_json    TEXT                           COMMENT '메타데이터 (JSON 문자열)',
    CONSTRAINT pk_rag_chunk PRIMARY KEY (chunk_id),
    CONSTRAINT fk_chunk_doc FOREIGN KEY (doc_id)
        REFERENCES rag_document (doc_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB COMMENT='RAG 검색용 청크 (문서 메타는 rag_document 에서 JOIN)';


-- =====================================================================
--  품질 리포트 : 관계 없는 단순 지표 테이블 (참고용)
-- =====================================================================
CREATE TABLE quality_report (
    metric VARCHAR(100)                             COMMENT '지표명',
    value  VARCHAR(500)                             COMMENT '값',
    note   VARCHAR(500)                             COMMENT '비고'
) ENGINE=InnoDB COMMENT='품질 리포트 (독립/검산)';
