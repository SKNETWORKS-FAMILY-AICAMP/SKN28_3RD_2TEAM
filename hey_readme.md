# 세션 작업 요약

## 브랜치 현황

| 브랜치 | 상태 |
|---|---|
| `KIM_SQL2` | 첫 번째 hjs 머지 상태 (`45b52c2`) |
| `KIM_SQL2_backup` | 머지 전 안전 백업 |
| `main` | 건드리지 않음 |

---

## 1. Git 작업

- `git fetch --all` 로 `hjs`, `sim` 브랜치 확인
- `KIM_SQL2_backup` 생성 (안전망)
- `hjs` 브랜치를 `KIM_SQL2`에 머지 × 2회
  - 1차: `.gitignore` 충돌 해결 후 머지
  - 2차: hjs에 새 커밋 추가돼서 재머지

---

## 2. Streamlit 실행 환경

- 실행 Python: `C:\Users\Playdata\miniforge3\envs\pystudy_env`
- `conda activate pystudy_env` 후 실행
- 실행 명령: `python -m streamlit run streamlit_app.py`
- 주소: `http://localhost:8501`

### 설치한 패키지
```
langchain-chroma
chromadb
pymysql
```

---

## 3. OpenAI + Vectorstore 설정

- `.env` 파일 생성 (프로젝트 루트)
  ```
  OPENAI_API_KEY=sk-...
  MYSQL_HOST=localhost
  MYSQL_USER=practice
  MYSQL_PASSWORD=practice
  MYSQL_DATABASE=kaist_ai
  ```
- Vectorstore 빌드 (최초 1회):
  ```
  python data/build_vectorstore.py --reset --smoke-test
  ```
- 모델: LLM `gpt-4.1-mini`, 임베딩 `text-embedding-3-small`

---

## 4. MySQL 연결

- MySQL Workbench 로컬 실행 중
- DB: `kaist_ai` / User: `practice`
- 주요 테이블: `person`, `course`, `admission`, `event`, `department`, `asset`

---

## 5. SQL 검색기 구현 (`src/rag/sql_retriever.py`)

hjs 브랜치에 없던 파일로 새로 작성:

### 주요 기능
| 기능 | 내용 |
|---|---|
| DB 접속 정보 | `.env`에서 읽음 (하드코딩 없음) |
| person-department JOIN | `dept` 코드 대신 `dept_name` 반환 |
| admission_type 필터 | 지원자격/일정/장학금 유형별 정확 필터 |
| degree level 필터 | "석사" 질문 → `title LIKE '%석사과정%'` |

### sql_table_hint → MySQL 테이블 매핑
```
professors    → person
courses       → course
admissions    → admission
events        → event
office_contacts → department
assets        → asset
```

---

## 6. RAG 파이프라인 연결

- `pages/3_RAG_Chatbot.py`에 `SqlRetriever` 연결
  ```python
  pipeline = RagPipeline(
      config=RagPipelineConfig(preload_vector_retriever=True),
      sql_retriever=SqlRetriever(),
  )
  ```
- `query_analyzer.py` 라우팅 수정:
  - "지원 자격", "입학 자격" 키워드 → `hybrid` 라우팅 (기존: `vector`)
  - `"자격"` 단어를 `VECTOR_STRONG_KEYWORDS`에서 제거

---

## 7. SQL 데이터 탐색 페이지

- `pages/4_SQL_Data.py` 신규 생성
- CSV 파일 12개를 테이블로 탐색
- 전체 컬럼 검색 기능

---

## 8. 팀원 논의 내용

### 핵심 문제 (팀원 공유)
- Vector 검색 `top-5`에서 정답이 안 잡힘
- "석사 지원 자격" 질문 시 "석박사 통합과정" 문서가 상위 노출
- `원서접수(서류제출포함)` 청크에 학위과정 메타데이터 없음

### 팀원 작업 방향
- `fetch_k` 늘려 후보 더 수집
- 석사/박사 유형별 재정렬
- 메타데이터에 `degree_level` 필드 추가 예정

### 우리 쪽 대응
- SQL이 `admission_type` + `title` 필터로 정확한 데이터 보완
- Vector 개선은 팀원 작업과 역할 분담

---

## 9. 현재 파일 구조 변경 사항

```
신규 생성:
  src/rag/sql_retriever.py     ← MySQL SQL 검색기
  pages/4_SQL_Data.py          ← 데이터 탐색 페이지
  README_POST_MERGE.md         ← 머지 이후 실행 가이드

수정:
  pages/3_RAG_Chatbot.py       ← SqlRetriever 연결
  src/rag/query_analyzer.py    ← 라우팅 수정
  requirements.txt             ← pymysql 추가
  .env                         ← MySQL 접속 정보 추가
```

---

## 10. 남은 과제

- [ ] 팀원 메타데이터 작업 머지 후 재테스트
- [ ] `sim` 브랜치 머지 검토
- [ ] Vectorstore 재빌드 (팀원 `degree_level` 추가 후)
- [ ] `README_POST_MERGE.md` → 팀 공유
