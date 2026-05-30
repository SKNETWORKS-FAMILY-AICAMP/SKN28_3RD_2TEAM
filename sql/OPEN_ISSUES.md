# SQL 스키마 — 미해결 / 후속 과제 (팀 공유용)

> ERD 리뷰 피드백 10개 중 **코드로 해결한 것**(영역 구분·RAG 중복 제거·키 전략 통일·ERD 재배치)은
> [`01_schema.sql`](01_schema.sql) / [`ERD.md`](ERD.md) / [`README.md`](README.md) 에 반영 완료.
> 이 문서는 **데이터 한계로 못 닫은 항목**만 모았습니다. 대부분 SQL이 아니라 **크롤링/수집 단계**의 협조가 필요합니다.

작성 기준일: 2026-05-31

---

## 요약

| # | 이슈 | 상태 | 막힌 이유 | 필요한 협조 |
|---|------|------|-----------|-------------|
| 3 | 교수↔과목 M:N 관계 | ❌ 미해결 | 크롤링 데이터에 교수-과목 연결 컬럼 없음 | 크롤러: 매핑 수집 |
| 6 | attachment 참조 대상 FK | 🟡 부분 | post_id가 record_id의 *부분 문자열* | 크롤러: 완전한 부모 ID 수집 |
| 2 | department 중심 N:1 과다 | 🟡 부분(표현만 개선) | 데이터 본질상 모두 학과 소속 | 구조 변경 불필요(설계 판단) |
| 1 | ERD가 CSV 스키마에 가까움 | 🟡 부분 | 개체 간 관계 부재(3번에 종속) | 3번 해결 시 동반 개선 |

---

## ❌ 3. 교수↔과목 M:N 관계 (최우선)

**현황**
- 리뷰 의견: "교수-강의 M:N 관계 검토 필요."
- 현재 모델에는 교수(`person`)와 과목(`course`)을 잇는 관계가 **없음**.

**원인 (실측)**
- `people_clean.csv` 헤더에 과목 참조 컬럼 없음.
- `courses_clean.csv` 헤더에 교수 참조 컬럼 없음.
- → 둘을 잇는 데이터가 **수집 단계에서부터 존재하지 않음**. 교차테이블을 만들면 빈 껍데기가 됨.

**영향**
- "이 교수가 어떤 과목을 가르치는가" 류 질의 불가 → RAG/검색 기능에서 교수-과목 연계 답변 불가.

**필요한 협조 — 크롤링 담당**
- 과목 상세/교수 상세 페이지에서 **담당 교수명 또는 교수 record_id** 를 함께 수집.
- 산출 형태 예시(CSV 한 장):

  | course_record_id | person_record_id | role |
  |------------------|------------------|------|
  | (course의 record_id) | (person의 record_id) | 주담당/공동 등 |

**확보되면 SQL 처리 (준비됨)**
- `course_track` 와 **동일한 교차 엔터티 패턴**으로 추가:
  ```sql
  CREATE TABLE course_person (
      course_id  VARCHAR(255) NOT NULL,   -- FK → course.record_id
      person_id  VARCHAR(255) NOT NULL,   -- FK → person.record_id
      role       VARCHAR(50),
      PRIMARY KEY (course_id, person_id), -- 복합키
      FOREIGN KEY (course_id) REFERENCES course(record_id),
      FOREIGN KEY (person_id) REFERENCES person(record_id)
  );
  ```

---

## 🟡 6. attachment 참조 대상 — 부분 해결

**현황**
- 리뷰 의견: "attachment 테이블의 참조 대상을 명확히."
- **명확화는 완료**: PDF 첨부의 실제 부모는 학과가 아니라 **게시글(post)** 이며,
  `(dept, board, post_id)` 가 출처 게시글을 가리킴. `board` 값에 따라 그 게시글은
  `admission`(입학 안내) 또는 `event`(공지)로 실체화됨. → 주석 + `(dept,board,post_id,filename)` UNIQUE 로 명시.

**못 한 부분 (왜)**
- `post_id` 가 admission/event 의 `record_id` **전체가 아니라 부분 문자열**임 (실측 확인).
  - 예: attachment `post_id = 학사과정 입학 안내_fecb9722e3`
    → admission `record_id = aic_admission_ug_학사과정 입학 안내_fecb9722e3_..._item_0001`
- 부분 문자열로는 **단일 FK 제약을 강제할 수 없음** → 현재는 `dept` 만 FK.

**필요한 협조 — 크롤링 담당**
- attachment 수집 시 **부모 게시글의 완전한 record_id** 를 함께 기록(`parent_record_id` 컬럼 추가).
- 그러면 board에 따라 admission/event 중 하나로 FK 연결 가능(다형 참조라 board 기준 분기 또는 공통 post 테이블 도입 검토).

---

## 🟡 2. department 중심 N:1 과다 — 표현만 개선 (구조 유지)

**현황**
- 리뷰 의견: "department 중심 N:1이 과도. 당연한 결과겠지만."
- **개선**: ERD를 3개 영역 도표로 분할해 한 도표당 dept 자식 수를 줄여 **가독성 확보**.

**구조를 안 바꾼 이유 (설계 판단)**
- 모든 데이터가 학과 소속이라 dept N:1 이 많은 것은 **데이터 본질**. 억지로 중간 계층을 넣으면 오히려 복잡.
- → 추가 작업 불필요로 판단. 팀 합의가 다르면 재논의 가능.

---

## 🟡 1. ERD가 크롤링 CSV 스키마에 가까움 — 부분 개선

**현황**
- 영역 분리·정규화·키 통일로 ERD다워졌으나, `person`/`course`/`admission`/`event` 가
  여전히 **dept만 참조하는 평면 구조**.

**남은 한계 (3번에 종속)**
- 개체 간 관계(교수-과목 등)가 생겨야 진짜 업무 모델로 깊어짐 → **3번이 풀리면 동반 개선**.

---

## 다음 스텝 제안

1. **크롤링 담당과 미팅** — 3번(교수-과목 매핑), 6번(부모 record_id) 수집 가능 여부 확인.
2. 수집 가능하면 → SQL 쪽은 위 `course_person` 패턴 + attachment `parent_record_id` 로 즉시 반영 가능.
3. 수집 불가하면 → 발표 시 **"관계는 식별했으나 수집 단계 한계로 후속 과제"** 로 명시(데이터 한계 이해를 보여주는 포인트).
