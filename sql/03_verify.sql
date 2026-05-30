-- =====================================================================
--  적재 검증 쿼리 모음
--  01_schema.sql → 02_load.sql 실행 후 돌려서 결과가 맞는지 확인한다.
--  (SQLD 조회 개념: COUNT/GROUP BY/HAVING/JOIN/서브쿼리/집합연산을 두루 사용)
-- =====================================================================
USE kaist_ai;

-- ---------------------------------------------------------------------
-- [A] 행 수 검증 : 각 테이블이 README 의 기대치와 맞는지
--   기대값  department 4 / person 246 / course 109 / admission 74 /
--           event 4 / asset 270 / attachment 4 / rag_document 482 /
--           rag_chunk 523 / quality_report 14
-- ---------------------------------------------------------------------
SELECT 'department'   AS table_name, COUNT(*) AS row_count FROM department
UNION ALL SELECT 'person',       COUNT(*) FROM person
UNION ALL SELECT 'course',       COUNT(*) FROM course
UNION ALL SELECT 'track',        COUNT(*) FROM track
UNION ALL SELECT 'course_track', COUNT(*) FROM course_track
UNION ALL SELECT 'admission',    COUNT(*) FROM admission
UNION ALL SELECT 'event',        COUNT(*) FROM event
UNION ALL SELECT 'asset',        COUNT(*) FROM asset
UNION ALL SELECT 'attachment',   COUNT(*) FROM attachment
UNION ALL SELECT 'rag_document', COUNT(*) FROM rag_document
UNION ALL SELECT 'rag_chunk',    COUNT(*) FROM rag_chunk
UNION ALL SELECT 'quality_report', COUNT(*) FROM quality_report;
-- UNION ALL 을 쓴 이유: 중복 제거가 필요 없고(테이블명이 모두 다름),
-- 중복 검사를 생략해 UNION 보다 빠르다. → 시험 단골 비교 포인트.


-- ---------------------------------------------------------------------
-- [B] 정규화 확인 : department 마스터에 학과 4개가 유일하게 들어갔나
-- ---------------------------------------------------------------------
SELECT dept, dept_name FROM department ORDER BY dept;


-- ---------------------------------------------------------------------
-- [C] 그룹 집계 : 학과별 교수 수 (GROUP BY + 정렬)
--   JOIN 으로 코드(dept) 대신 한글 학과명을 같이 보여준다.
-- ---------------------------------------------------------------------
SELECT d.dept_name, COUNT(*) AS faculty_count
FROM person p
JOIN department d ON d.dept = p.dept
GROUP BY d.dept_name
ORDER BY faculty_count DESC;


-- ---------------------------------------------------------------------
-- [D] HAVING : 교과목이 20개를 넘는 학과만 (집계 결과에 조건)
--   WHERE 는 집계 전 행을, HAVING 은 집계 후 그룹을 거른다. (시험 핵심)
-- ---------------------------------------------------------------------
SELECT d.dept_name, COUNT(*) AS course_count
FROM course c
JOIN department d ON d.dept = c.dept
GROUP BY d.dept_name
HAVING COUNT(*) > 20
ORDER BY course_count DESC;


-- ---------------------------------------------------------------------
-- [E] M:N 검증 : 한 과목이 여러 트랙에 속하는 사례 Top 5
--   course_track(교차 엔터티)을 양쪽 마스터와 JOIN.
-- ---------------------------------------------------------------------
SELECT c.course_code, c.course_name, COUNT(*) AS track_count
FROM course_track ct
JOIN course c ON c.record_id = ct.course_id
GROUP BY c.course_code, c.course_name
HAVING COUNT(*) >= 2
ORDER BY track_count DESC, c.course_code
LIMIT 5;


-- ---------------------------------------------------------------------
-- [F] 특정 과목의 트랙 목록 : 3중 JOIN (course - course_track - track)
-- ---------------------------------------------------------------------
SELECT c.course_code, c.course_name, t.track_name, ct.course_type
FROM course_track ct
JOIN course c ON c.record_id = ct.course_id
JOIN track  t ON t.track_id  = ct.track_id
ORDER BY c.course_code, t.track_name
LIMIT 20;


-- ---------------------------------------------------------------------
-- [G] 참조 무결성 점검 : '부모 없는 자식'(고아 행)이 있나
--   FK 가 제대로 걸렸다면 결과는 0건이어야 정상.
--   LEFT JOIN 후 부모가 NULL 인 행을 찾는 안티조인 패턴.
-- ---------------------------------------------------------------------
SELECT p.record_id
FROM person p
LEFT JOIN department d ON d.dept = p.dept
WHERE d.dept IS NULL;          -- 0건이면 무결성 OK


-- ---------------------------------------------------------------------
-- [H] NULL 분석 : 이메일이 없는 교수 비율 (IS NULL + 집계)
--   missing_fields 와 실제 NULL 이 일치하는지 가늠.
-- ---------------------------------------------------------------------
SELECT
    COUNT(*)                                   AS total,
    SUM(email IS NULL)                         AS email_missing,
    ROUND(SUM(email IS NULL) / COUNT(*) * 100, 1) AS missing_pct
FROM person;


-- ---------------------------------------------------------------------
-- [I] 서브쿼리 : 평균(학과별 교수 수)보다 교수가 많은 학과
--   FROM 절 서브쿼리(인라인 뷰) + 스칼라 서브쿼리 조합.
-- ---------------------------------------------------------------------
SELECT x.dept_name, x.cnt
FROM (
    SELECT d.dept_name, COUNT(*) AS cnt
    FROM person p
    JOIN department d ON d.dept = p.dept
    GROUP BY d.dept_name
) AS x
WHERE x.cnt > (
    SELECT AVG(cnt) FROM (
        SELECT COUNT(*) AS cnt FROM person GROUP BY dept
    ) AS y
)
ORDER BY x.cnt DESC;


-- ---------------------------------------------------------------------
-- [J] 정규화(3NF) 정리 결과 확인 : 학과별 RAG 청크 수
--   rag_chunk 에서 dept 를 제거했으므로 학과는 rag_document 를 거쳐 얻는다.
--     rag_chunk → (doc_id) → rag_document → (dept) → department
--   "중복 컬럼을 지워도 JOIN 으로 같은 정보를 얻는다"는 정규화의 핵심을 보여준다.
-- ---------------------------------------------------------------------
SELECT d.dept_name, COUNT(*) AS chunk_count
FROM rag_chunk ch
JOIN rag_document rd ON rd.doc_id = ch.doc_id
JOIN department  d  ON d.dept    = rd.dept
GROUP BY d.dept_name
ORDER BY chunk_count DESC;
