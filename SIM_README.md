# KAIST AI College RAG Chatbot README

## 1. 이 코드는 무엇을 하나요?

이 코드는 KAIST AI대학 관련 데이터를 기반으로 사용자의 질문에 답변하는 **Streamlit 기반 RAG 챗봇**입니다.

사용자가 질문을 입력하면 다음 과정을 거쳐 답변을 생성합니다.

```text
사용자 질문
→ 질문 분석
→ SQL / Vector / Hybrid / Clarify route 결정
→ 필요한 데이터 검색 또는 조회
→ LLM용 context 생성
→ OpenAI LLM 답변 생성
→ Streamlit 화면 출력
```

현재 구현된 구조는 다음 4가지 route를 사용합니다.

| route | 의미 | 예시 질문 |
|---|---|---|
| `vector` | 문서 검색 기반 답변 | AI컴퓨팅학과 학과설명회 정보 알려줘 |
| `sql` | 정형 데이터 조회 | AI시스템학과 교과목 알려줘 |
| `hybrid` | SQL 조회 + Vector 검색 | AI시스템학과 교과목 목록과 각 과목 설명도 알려줘 |
| `clarify` | 질문 정보 부족 | 교수진도 알려줘 |

---

## 2. 폴더 구조

현재 프로젝트 구조는 다음과 같습니다.

```text
C:.
├─ .vscode
├─ assets
├─ components
│  ├─ __init__.py
│  ├─ layout.py
│  └─ styles.py
├─ data
│  ├─ processed
│  │  ├─ csv
│  │  ├─ json
│  │  └─ reports
│  ├─ raw_data
│  └─ vectorstore
│      └─ chroma_db
├─ pages
│  ├─ 1_AI_College_Intro.py
│  ├─ 2_Departments.py
│  └─ 3_RAG_Chatbot.py
├─ src
│  └─ rag
│     ├─ query_analyzer.py
│     ├─ vector_retriever.py
│     ├─ context_builder.py
│     ├─ answer_generator.py
│     ├─ rag_pipeline.py
│     ├─ sql_tool.py
│     └─ rag_tests.py
├─ streamlit_app.py
├─ requirements.txt
├─ .gitignore
└─ README.md
```

주요 폴더 역할은 다음과 같습니다.

| 폴더 | 역할 |
|---|---|
| `assets/` | Streamlit 화면에서 사용하는 이미지 파일 |
| `components/` | Streamlit UI 컴포넌트와 CSS |
| `pages/` | Streamlit 멀티페이지 화면 |
| `src/rag/` | RAG 핵심 로직 |
| `data/raw_data/` | 원본 데이터 |
| `data/processed/csv/` | SQL DB에 넣을 정형 CSV |
| `data/processed/json/` | Vectorstore 생성용 JSON/JSONL |
| `data/vectorstore/chroma_db/` | Chroma Vectorstore 저장 위치 |

---

## 3. 실행 전 준비사항

### 3.1 가상환경 활성화

현재 개발 기준 가상환경은 `dl_nlp_env`입니다.

```powershell
conda activate dl_nlp_env
```

### 3.2 패키지 설치

프로젝트 루트에서 다음 명령어를 실행합니다.

```powershell
pip install -r requirements.txt
```

현재 프로젝트에 필요한 주요 패키지는 다음과 같습니다.

```txt
streamlit
pandas
openpyxl

python-dotenv
tqdm

langchain-core
langchain-openai
langchain-chroma
chromadb
tiktoken
```

### 3.3 `.env` 파일 설정

프로젝트 루트에 `.env` 파일을 만들고 OpenAI API Key를 설정합니다.

```env
OPENAI_API_KEY=your_openai_api_key
```

SQL DB 파일 위치가 기본 경로와 다르면 아래 환경변수를 추가합니다.

```env
KAIST_SQL_DB_PATH=C:\Users\Playdata\workspace\SKN28-third-2TEAM\data\database\kaist_ai.db
```

기본 SQL DB 경로는 다음과 같습니다.

```text
data/database/kaist_ai.db
```

### 3.4 Vectorstore 준비

Vectorstore는 아래 위치에 있어야 합니다.

```text
data/vectorstore/chroma_db
```

기본 collection 이름은 다음과 같습니다.

```text
kaist_graduate_info
```

### 3.5 SQL DB 준비

SQL DB는 SQL 담당자가 생성합니다.

기본적으로 아래 경로에 DB 파일이 있으면 `sql_tool.py`가 자동으로 사용합니다.

```text
data/database/kaist_ai.db
```

다른 경로에 있다면 `.env`의 `KAIST_SQL_DB_PATH` 값을 수정합니다.

---

## 4. 실행 방법

### 4.1 Streamlit 앱 실행

```powershell
streamlit run streamlit_app.py
```

### 4.2 질문 분석 테스트

```powershell
python src/rag/query_analyzer.py
```

### 4.3 Vector 검색 테스트

```powershell
python src/rag/vector_retriever.py
```

### 4.4 SQL Tool 테스트

```powershell
python src/rag/sql_tool.py
```

SQL DB 파일이 없으면 아래 메시지가 나옵니다.

```text
SQL DB 파일을 찾을 수 없습니다.
DB 경로를 확인하세요: ...data\database\kaist_ai.db
KAIST_SQL_DB_PATH 환경변수로 DB 경로를 지정할 수 있습니다.
```

이 메시지는 SQL Tool 오류가 아니라, SQL DB 파일이 아직 연결되지 않았다는 뜻입니다.

### 4.5 전체 RAG Pipeline 테스트

```powershell
python src/rag/rag_pipeline.py
```

### 4.6 전체 질문 테스트

```powershell
python src/rag/rag_tests.py
```

---

## 5. 주요 코드 흐름

전체 RAG 흐름은 다음과 같습니다.

```text
사용자 질문
↓
query_analyzer.py
↓
route 결정
├─ vector  → vector_retriever.py
├─ sql     → sql_tool.py
├─ hybrid  → vector_retriever.py + sql_tool.py
└─ clarify → 추가 질문 반환
↓
context_builder.py
↓
answer_generator.py
↓
rag_pipeline.py
↓
Streamlit 화면 출력
```

### 5.1 Vector 질문 흐름

예시 질문:

```text
AI컴퓨팅학과 학과설명회 정보 알려줘
```

처리 흐름:

```text
query_analyzer.py
→ route = vector
→ vector_retriever.py에서 Chroma 검색
→ context_builder.py에서 검색 결과를 context로 변환
→ answer_generator.py에서 답변 생성
→ Streamlit에 답변과 출처 표시
```

### 5.2 SQL 질문 흐름

예시 질문:

```text
AI시스템학과 교과목 알려줘
```

처리 흐름:

```text
query_analyzer.py
→ route = sql
→ sql_tool.py에서 course 테이블 조회
→ context_builder.py에서 SQL 결과를 context로 변환
→ answer_generator.py에서 답변 생성
→ Streamlit에 답변 표시
```

### 5.3 Hybrid 질문 흐름

예시 질문:

```text
AI시스템학과 교과목 목록과 각 과목 설명도 알려줘
```

처리 흐름:

```text
query_analyzer.py
→ route = hybrid
→ vector_retriever.py에서 문서 검색
→ sql_tool.py에서 정형 데이터 조회
→ context_builder.py에서 Vector + SQL context 생성
→ answer_generator.py에서 답변 생성
```

### 5.4 Clarify 질문 흐름

예시 질문:

```text
교수진도 알려줘
```

처리 흐름:

```text
query_analyzer.py
→ route = clarify
→ "어느 학과에 대한 질문인지 알려주세요" 메시지 반환
```

---

## 6. 입력 데이터 / 출력 데이터

### 6.1 입력 데이터

| 데이터 | 경로 | 사용 위치 |
|---|---|---|
| 전처리 CSV | `data/processed/csv/` | SQL DB 생성용 |
| Vector 문서 JSONL | `data/processed/json/vector_documents.jsonl` | Chroma Vectorstore 생성용 |
| Chroma DB | `data/vectorstore/chroma_db/` | Vector 검색 |
| SQLite DB | `data/database/kaist_ai.db` | SQL 조회 |
| `.env` | `.env` | API Key, DB 경로 설정 |

### 6.2 출력 데이터

| 출력 | 설명 |
|---|---|
| `answer` | 최종 답변 |
| `route` | 질문 처리 방식 |
| `status` | 처리 상태 |
| `sources` | Streamlit 출처 카드용 데이터 |
| `warnings` | 경고 메시지 |
| `debug` | 개발자 확인용 상세 정보 |
| `rag_test_results.json` | 테스트 결과 리포트 |

테스트 리포트 저장 경로:

```text
data/processed/reports/rag_test_results.json
```

### 6.3 Streamlit 응답 객체 예시

`rag_pipeline.py`의 `RAGPipeline.ask()`는 다음 형태의 응답을 반환합니다.

```python
RAGPipelineResponse(
    answer="...",
    route="vector",
    status="searched",
    sources=[...],
    warnings=[...],
    debug={...}
)
```

---

## 7. 주요 함수 설명

### 7.1 `query_analyzer.py`

#### `QuestionAnalyzer.analyze(question, previous_department_code=None)`

사용자 질문을 분석해 `QueryAnalysis` 객체를 반환합니다.

반환 정보:

| 필드 | 설명 |
|---|---|
| `route` | `vector`, `sql`, `hybrid`, `clarify` |
| `department_name` | 학과명 |
| `department_code` | 학과 코드 |
| `intent` | 질문 의도 |
| `content_type` | 문서 유형 |
| `program_type` | 석사/박사/석박사 통합과정 구분 |
| `metadata_filter` | Vector 검색 필터 |
| `sql_table_hint` | SQL 조회 대상 힌트 |
| `sql_task_hint` | SQL 작업 힌트 |
| `sql_conditions` | SQL 조회 조건 |

---

### 7.2 `vector_retriever.py`

#### `VectorRetriever.retrieve(question, previous_department_code=None, force_vector_search=False)`

질문에 맞는 문서를 Chroma Vectorstore에서 검색합니다.

반환값:

```python
VectorRetrievalResult
```

주요 필드:

| 필드 | 설명 |
|---|---|
| `status` | 검색 상태 |
| `results` | 검색된 문서 리스트 |
| `used_query` | 실제 검색에 사용한 질문 |
| `used_filter` | 사용된 metadata filter |
| `used_fallback` | fallback 사용 여부 |
| `warnings` | 검색 경고 |
| `analysis` | 질문 분석 결과 |

---

### 7.3 `context_builder.py`

#### `ContextBuilder.build(analysis, vector_result=None, sql_result=None)`

검색 결과와 SQL 결과를 LLM context로 변환합니다.

반환값:

```python
BuiltContext
```

주요 필드:

| 필드 | 설명 |
|---|---|
| `context` | LLM에 전달할 전체 context |
| `vector_context` | Vector 검색 결과 context |
| `sql_context` | SQL 조회 결과 context |
| `sources` | 출처 정보 |
| `warnings` | 경고 정보 |

---

### 7.4 `answer_generator.py`

#### `AnswerGenerator.generate(question, built_context, analysis=None)`

LLM을 호출해 최종 답변을 생성합니다.

반환값:

```python
GeneratedAnswer
```

주요 필드:

| 필드 | 설명 |
|---|---|
| `answer` | 최종 답변 |
| `sources` | 답변에 사용된 출처 |
| `warnings` | 경고 |
| `raw_context` | LLM에 전달된 context |

---

### 7.5 `sql_tool.py`

#### `SQLTool.query(analysis)`

`QueryAnalysis`의 `sql_task_hint`를 보고 적절한 SQL 테이블을 조회합니다.

반환값:

```python
SqlQueryResult
```

지원 task:

| task | 조회 테이블 |
|---|---|
| `course_lookup` | `course` |
| `person_lookup` | `person` |
| `office_contact_lookup` | `asset` |
| `admission_lookup` | `admission` |
| `event_lookup` | `event` |
| `asset_lookup` | `asset` |
| `department_overview` | `department` |

---

### 7.6 `rag_pipeline.py`

#### `RAGPipeline.ask(question, previous_department_code=None)`

전체 RAG 흐름을 실행하는 함수입니다.

처리 순서:

```text
질문 분석
→ route 확인
→ Vector / SQL / Hybrid 실행
→ context 생성
→ 답변 생성
→ RAGPipelineResponse 반환
```

Streamlit에서는 이 함수만 호출하면 됩니다.

---

## 8. 수정할 때 확인할 부분

### 8.1 학과명이 추가되는 경우

수정 파일:

```text
src/rag/query_analyzer.py
```

수정 위치:

```python
DEPARTMENTS
```

새 학과명, 학과 코드, 검색 키워드를 추가해야 합니다.

---

### 8.2 질문 의도가 추가되는 경우

수정 파일:

```text
src/rag/query_analyzer.py
```

수정 위치:

```python
INTENT_RULES
```

새 intent, content_type, keywords, vector_search_terms, sql_table_hint, sql_task_hint를 추가합니다.

---

### 8.3 SQL 테이블이나 컬럼이 바뀌는 경우

수정 파일:

```text
src/rag/sql_tool.py
```

확인할 부분:

- 테이블명
- 컬럼명
- JOIN 조건
- `sql_task_hint`와 실제 조회 함수 연결

---

### 8.4 Vectorstore 경로가 바뀌는 경우

수정 파일:

```text
src/rag/vector_retriever.py
```

확인할 설정:

```python
VectorRetrieverConfig.chroma_relative_dir
VectorRetrieverConfig.collection_name
```

---

### 8.5 OpenAI 모델을 바꾸는 경우

수정 파일:

```text
src/rag/answer_generator.py
```

확인할 설정:

```python
AnswerGeneratorConfig.model
```

현재 기본값:

```python
model = "gpt-4.1-mini"
```

---

### 8.6 Streamlit 화면을 수정하는 경우

수정 파일:

```text
streamlit_app.py
pages/3_RAG_Chatbot.py
components/layout.py
components/styles.py
```

RAG 결과는 `RAGPipeline.ask()`에서 반환되는 아래 필드를 사용합니다.

```python
result.answer
result.sources
result.warnings
result.debug
```

---

## 9. 현재까지 구현된 기능

### 9.1 질문 분석

- 학과명 인식
- 질문 의도 분류
- route 결정
- Vector metadata filter 생성
- SQL 조회 조건 생성
- 석사/박사/석박사 통합과정 구분

### 9.2 Vector RAG

- Chroma DB 연결
- OpenAI Embedding 사용
- metadata filter 검색
- fallback retrieval
- lightweight reranking
- 출처 정보 반환

### 9.3 SQL Tool

- SQLite DB 연결 구조
- SQL task별 조회 함수
- DB 파일 없음 warning 처리
- 테이블 없음 warning 처리
- SQL 조회 결과를 `SqlQueryResult`로 반환

### 9.4 Context Builder

- 질문 분석 정보 context 생성
- Vector 검색 결과 context 생성
- SQL 조회 결과 context 생성
- source 목록 생성
- warning 목록 생성

### 9.5 Answer Generator

- OpenAI LLM 호출
- context 기반 답변 생성
- 근거 없는 내용 확인 불가 처리
- 출처 표시

### 9.6 Streamlit UI

- 멀티페이지 앱 구조
- 챗봇 페이지
- Quick Question 버튼
- 답변 출력
- Retrieved Sources 카드
- warning 출력
- Debug 출력

---

## 10. 아직 개선이 필요한 부분

### 10.1 SQL DB 없음 처리

현재 SQL DB가 없을 때도 LLM 답변 생성을 시도할 수 있습니다.

개선 방향:

```text
SQL DB가 연결되지 않은 경우 LLM 호출 없이 시스템 안내 메시지 반환
```

예상 메시지:

```text
현재 SQL DB가 연결되지 않아 정형 데이터를 조회할 수 없습니다.
DB 파일 경로를 확인하거나 KAIST_SQL_DB_PATH 환경변수를 설정해주세요.
```

---

### 10.2 Debug 표시 옵션화

현재 Debug 정보가 화면에 보일 수 있습니다.

개선 방향:

```python
show_debug = st.sidebar.toggle("Debug 보기", value=False)
```

개발 중에는 켜고, 발표용 화면에서는 기본적으로 숨기는 방식이 좋습니다.

---

### 10.3 테스트 자동화 강화

현재 테스트는 출력 확인 중심입니다.

개선 방향:

```text
expected_route
expected_top_content_type
expected_top_title_contains
expected_status
```

기준으로 PASS/FAIL을 자동 출력하도록 개선합니다.

---

### 10.4 Reranker 점수 체계 정리

현재 reranker는 keyword, metadata, vector score 등을 사용하지만 점수 구조를 더 명확히 정리할 필요가 있습니다.

개선 방향:

```text
metadata_score
title_match_score
section_match_score
intent_match_score
keyword_score
vector_score
fallback_penalty
```

---

### 10.5 Source Card 정렬 및 중복 제거

답변에 사용된 근거와 Retrieved Sources 카드 순서가 다르게 보일 수 있습니다.

개선 방향:

- `vector_result.results` 기준 정렬
- title/source/content_type 기준 중복 제거
- fallback 문서는 별도 표시

---

### 10.6 Overview 문서 타입 추가

학과 소개 질문 품질을 높이려면 학과 소개 문서에 별도 `content_type`을 부여하는 것이 좋습니다.

예상 content_type:

```text
overview
```

예시 질문:

```text
AI컴퓨팅학과는 어떤 학과야?
AI미래학과 소개해줘
AX학과 특징 알려줘
```

---

### 10.7 교수 연구분야 데이터 보강

교수 연구분야 답변은 원본 데이터에 `research_area`가 있어야 좋아집니다.

보강하면 좋은 필드:

```text
research_area
research_field
lab
homepage
profile_url
```

---

### 10.8 사용하지 않는 데모 파일 정리

실제 RAG Pipeline을 연결한 후 `data/demo_knowledge.py`가 더 이상 사용되지 않으면 삭제할 수 있습니다.

삭제 전 확인 명령어:

```powershell
Select-String -Path *.py,pages/*.py,components/*.py,src/**/*.py -Pattern "demo_knowledge|get_demo_response"
```
