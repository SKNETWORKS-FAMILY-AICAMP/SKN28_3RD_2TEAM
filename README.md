# SKN28 3rd 2TEAM - KAIST AI College RAG Chatbot

> KAIST AI 관련 학과의 입학, 교과목, 교수진, 학과 소개, 연락처, 자료 링크 정보를 기반으로 사용자의 질문에 답변하는 **Streamlit 기반 RAG 챗봇 프로젝트**입니다.

---

## 1. 프로젝트 개요

본 프로젝트는 KAIST AI 관련 학과 정보를 수집·전처리한 뒤, 정형 데이터는 MySQL에 저장하고 비정형 문서 데이터는 Chroma VectorStore에 저장하여 사용자의 질문에 근거 기반 답변을 제공하는 RAG 시스템입니다.

사용자는 Streamlit 화면에서 자연어로 질문할 수 있으며, 시스템은 질문의 의도와 대상 학과를 분석한 뒤 SQL 조회, Vector 검색, 또는 두 방식을 함께 사용하는 Hybrid 검색을 수행합니다. 이후 검색 결과를 LLM에 전달하여 최종 답변과 출처를 생성합니다.

---

## 2. 팀원

| 이름 |
|---|
| 김성재 |
| 손지은 |
| 신혜지 |
| 심기성 |

---

## 3. 주요 기능

- KAIST AI 관련 학과 정보 기반 질의응답
- Streamlit 기반 멀티페이지 웹 애플리케이션
- 학과별 입학 정보, 교과목, 교수진, 연락처, 학과 소개 조회
- MySQL 기반 정형 데이터 검색
- Chroma VectorStore 기반 문서 검색
- SQL 검색과 Vector 검색을 결합한 Hybrid RAG 구조
- 질문 의도, 학과, 검색 route 자동 분석
- 대화 맥락을 활용한 후속 질문 처리
- 동일 질문 캐시 및 RAG 검색기 warm-up
- 답변 출처 카드 표시
- 개인별 합격 가능성, 합격 확률, 합격 여부 예측 질문 차단
- 테스트 노트북 및 챗봇 평가 결과 저장

---

## 4. 지원 학과

현재 프로젝트는 수집된 KAIST AI 관련 4개 학과 데이터를 중심으로 동작합니다.

| 학과명 | 코드 |
|---|---|
| AI컴퓨팅학과 | `aic` |
| AI시스템학과 | `ai_systems` |
| AX학과 | `ax` |
| AI미래학과 | `fx` |

---

## 5. 지원 질문 유형

| 질문 유형 | 설명 | 예시 |
|---|---|---|
| 입학 정보 | 지원 자격, 전형, 일정, 제출서류 | `AI컴퓨팅학과 석사 지원 자격은?` |
| 교과목 정보 | 커리큘럼, 과목명, 트랙 | `AI시스템학과 교과목 알려줘` |
| 교수진 정보 | 교수명, 이메일, 연구분야 | `AX학과 교수진 알려줘` |
| 학과 연락처 | 사무실, 전화번호, 위치 | `AI미래학과 사무실 연락처 알려줘` |
| 학과 소개 | 학과 개요, 특징, 설명 | `AI컴퓨팅학과는 어떤 학과야?` |
| 자료 링크 | 홈페이지, PDF, 관련 링크 | `AI시스템학과 공식 링크 알려줘` |
| 비교 질문 | 여러 학과 비교 | `AI컴퓨팅학과와 AI시스템학과 차이를 알려줘` |

---

## 6. 전체 시스템 구조

```text
사용자 질문
    ↓
Streamlit UI
    ↓
RagPipeline
    ↓
QuestionAnalyzer
    ├─ 질문 의도 분석
    ├─ 학과명 추출
    ├─ 검색 route 결정
    └─ 답변 정책 검사
    ↓
검색 단계
    ├─ SQLTool: MySQL 정형 데이터 조회
    ├─ VectorRetriever: Chroma 문서 검색
    └─ Hybrid Search: SQL + Vector 통합 검색
    ↓
ContextBuilder
    ↓
AnswerGenerator
    ↓
LLM 답변 생성
    ↓
답변 / 출처 / warning 반환
```

검색 route는 질문 유형에 따라 다음 중 하나로 결정됩니다.

| route | 역할 |
|---|---|
| `sql` | 교수진, 교과목, 연락처처럼 정형 데이터 조회가 적합한 질문 처리 |
| `vector` | PDF, 학과 소개, 모집요강 등 문서 기반 설명 질문 처리 |
| `hybrid` | 정형 데이터와 문서 설명이 함께 필요한 질문 처리 |
| `clarify` | 질문 대상이 불명확해 추가 확인이 필요한 질문 처리 |

---

## 7. 프로젝트 구조

```text
SKN28-third-2TEAM/
├─ assets/
│  └─ kaist.jpg
│
├─ components/
│  ├─ __init__.py
│  ├─ layout.py
│  └─ styles.py
│
├─ data/
│  ├─ preprocessing.py
│  ├─ build_vectorstore.py
│  ├─ demo_knowledge.py
│  │
│  ├─ raw_data/
│  │  ├─ admissions_clean.csv
│  │  ├─ assets_clean.csv
│  │  ├─ attachments_clean.csv
│  │  ├─ course_track_map.csv
│  │  ├─ courses_clean.csv
│  │  ├─ events_clean.csv
│  │  ├─ people_clean.csv
│  │  ├─ quality_report.csv
│  │  ├─ AI_Computing_Grad_Info_Session_20260320.pdf
│  │  ├─ AI_Systems_Grad_Info_20260319.pdf
│  │  ├─ KAIST AI & FUTURES STUDIES.pdf
│  │  ├─ KAIST AX (AI Transformation).pdf
│  │  ├─ 손지은_KAIST_공식홈페이지_조사 - 기본정보.csv
│  │  └─ 손지은_KAIST_공식홈페이지_조사 - 학과사무실.csv
│  │
│  ├─ processed/
│  │  ├─ csv/
│  │  ├─ json/
│  │  └─ reports/
│  │
│  └─ vectorstore/
│     └─ chroma_db/
│
├─ notebooks/
│  ├─ rag_test.ipynb
│  └─ chatbot_eval_outputs/
│
├─ pages/
│  ├─ 1_AI_College_Intro.py
│  ├─ 2_Departments.py
│  └─ 3_RAG_Chatbot.py
│
├─ sql/
│  ├─ 01_schema.sql
│  ├─ 02_load.sql
│  ├─ 03_verify.sql
│  ├─ ERD.md
│  ├─ OPEN_ISSUES.md
│  └─ README.md
│
├─ src/
│  └─ rag/
│     ├─ query_analyzer.py
│     ├─ vector_retriever.py
│     ├─ sql_tool.py
│     ├─ context_builder.py
│     ├─ answer_generator.py
│     ├─ rag_pipeline.py
│     └─ rag_tests.py
│
├─ .streamlit/
│  └─ config.toml
├─ .gitignore
├─ requirements.txt
├─ streamlit_app.py
└─ README.md
```

---

## 8. 데이터 구성

### 8.1 원본 데이터

원본 데이터는 `data/raw_data/`에 저장되어 있습니다.

| 데이터 | 설명 |
|---|---|
| `admissions_clean.csv` | 입학 및 모집 관련 정보 |
| `courses_clean.csv` | 학과별 교과목 정보 |
| `course_track_map.csv` | 교과목과 트랙 매핑 정보 |
| `people_clean.csv` | 교수진 및 구성원 정보 |
| `events_clean.csv` | 설명회, 행사, 공지 관련 정보 |
| `assets_clean.csv` | 링크, 이미지, 홈페이지 자료 정보 |
| `attachments_clean.csv` | 첨부파일 메타데이터 |
| `quality_report.csv` | 데이터 품질 점검 결과 |
| `*.pdf` | 학과 설명회 및 학과 소개 PDF 자료 |
| `손지은_KAIST_공식홈페이지_조사 - 기본정보.csv` | KAIST 기본 정보 |
| `손지은_KAIST_공식홈페이지_조사 - 학과사무실.csv` | 학과 사무실 연락처 정보 |

### 8.2 전처리 결과

전처리 결과는 `data/processed/` 아래에 저장됩니다.

| 경로 | 역할 |
|---|---|
| `data/processed/csv/` | MySQL 적재용 정형 CSV |
| `data/processed/json/` | VectorStore 생성용 JSON/JSONL |
| `data/processed/reports/` | 전처리 리포트 및 테스트 결과 |

주요 전처리 산출물 규모는 다음과 같습니다.

| 파일 | 행/문서 수 |
|---|---:|
| `admissions.csv` | 74 |
| `courses.csv` | 109 |
| `course_track_map.csv` | 206 |
| `people.csv` | 246 |
| `events.csv` | 4 |
| `assets.csv` | 494 |
| `attachments.csv` | 4 |
| `department_offices.csv` | 42 |
| `kaist_profile.csv` | 28 |
| `kaist_statistics.csv` | 16 |
| `kaist_links.csv` | 7 |
| `quality_report.csv` | 14 |
| `vector_documents.jsonl` | 704 |

---

## 9. 기술 스택

| 구분 | 사용 기술 |
|---|---|
| Language | Python |
| Web UI | Streamlit |
| LLM | OpenAI API |
| RAG Framework | LangChain |
| Vector DB | ChromaDB |
| Embedding Model | `text-embedding-3-small` |
| SQL DB | MySQL |
| Data Processing | pandas, PyMuPDF |
| Environment | python-dotenv |
| Test/Experiment | Jupyter Notebook |

---

## 10. 설치 및 환경 설정

### 10.1 프로젝트 클론 또는 압축 해제

```powershell
cd C:\Users\Playdata\workspace\SKN28-third-2TEAM
```

### 10.2 가상환경 활성화

사용 중인 Python 가상환경을 활성화합니다.

```powershell
conda activate dl_nlp_env
```

또는 `venv`를 사용하는 경우:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 10.3 패키지 설치

```powershell
pip install -r requirements.txt
```

설치되는 주요 패키지는 다음과 같습니다.

```text
streamlit
python-dotenv
pandas
pymysql
tqdm
langchain
langchain-core
langchain-openai
langchain-chroma
chromadb
openai
pymupdf
```

### 10.4 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 값을 입력합니다.

```env
OPENAI_API_KEY=your_openai_api_key

KAIST_MYSQL_HOST=127.0.0.1
KAIST_MYSQL_PORT=3306
KAIST_MYSQL_USER=root
KAIST_MYSQL_PASSWORD=your_mysql_password
KAIST_MYSQL_DATABASE=kaist_ai
KAIST_SQL_MAX_ROWS=100
KAIST_MYSQL_CONNECT_TIMEOUT=5
```

---

## 11. 데이터 전처리

원본 CSV와 PDF를 기반으로 SQL 적재용 CSV와 VectorStore 적재용 JSONL을 생성합니다.

```powershell
python data\preprocessing.py
```

전처리 후 생성되는 주요 파일은 다음과 같습니다.

```text
data/processed/csv/admissions.csv
data/processed/csv/courses.csv
data/processed/csv/people.csv
data/processed/csv/department_offices.csv
data/processed/json/vector_documents.json
data/processed/json/vector_documents.jsonl
data/processed/reports/preprocess_summary.csv
```

---

## 12. MySQL DB 생성 및 데이터 적재

정형 데이터 검색을 사용하려면 MySQL에 데이터베이스와 테이블을 생성한 뒤 CSV 데이터를 적재합니다.

### 12.1 스키마 생성

```powershell
mysql -u root -p --local-infile=1 < sql\01_schema.sql
```

### 12.2 데이터 적재

```powershell
mysql -u root -p --local-infile=1 kaist_ai < sql\02_load.sql
```

### 12.3 적재 결과 검증

```powershell
mysql -u root -p --local-infile=1 kaist_ai < sql\03_verify.sql
```

적재된 데이터는 `src/rag/sql_tool.py`의 `SQLTool`을 통해 조회됩니다.

---

## 13. VectorStore 생성

비정형 문서 검색을 위해 `vector_documents.jsonl`을 Chroma VectorStore로 변환합니다.

```powershell
python data\build_vectorstore.py --reset --smoke-test
```

기본 설정은 다음과 같습니다.

| 항목 | 값 |
|---|---|
| 입력 파일 | `data/processed/json/vector_documents.jsonl` |
| 저장 위치 | `data/vectorstore/chroma_db` |
| Collection | `kaist_graduate_info` |
| Embedding Model | `text-embedding-3-small` |

옵션을 명시해서 실행할 수도 있습니다.

```powershell
python data\build_vectorstore.py `
  --project-root "." `
  --jsonl-path "data/processed/json/vector_documents.jsonl" `
  --chroma-dir "data/vectorstore/chroma_db" `
  --embedding-model "text-embedding-3-small" `
  --reset `
  --smoke-test
```

---

## 14. Streamlit 앱 실행

프로젝트 루트에서 다음 명령어를 실행합니다.

```powershell
python -m streamlit run streamlit_app.py
```

브라우저에서 Streamlit 앱이 열리면 다음 페이지를 사용할 수 있습니다.

| 페이지 | 설명 |
|---|---|
| AI College Intro | KAIST AI 관련 학과 프로젝트 소개 |
| Departments | 학과별 정보 요약 |
| RAG Chatbot | 자연어 질문 기반 RAG 챗봇 |

---

## 15. RAG 파이프라인 사용 예시

Streamlit 없이 Python 코드에서 직접 파이프라인을 사용할 수도 있습니다.

```python
from src.rag.rag_pipeline import create_default_pipeline

pipeline = create_default_pipeline(include_sql=True)
result = pipeline.run("AI컴퓨팅학과 석사 지원 자격은?")

print(result.answer)
print(result.sources)
print(result.warnings)
```

질문 분석 결과만 확인할 수도 있습니다.

```python
from src.rag.rag_pipeline import create_default_pipeline

pipeline = create_default_pipeline(include_sql=True)
analysis = pipeline.classify_question("AI시스템학과 교과목 알려줘")

print(analysis.to_dict())
```

---

## 16. 주요 모듈 설명

### `src/rag/query_analyzer.py`

사용자 질문을 분석하는 모듈입니다.

- 학과명 추출
- 질문 intent 분류
- 검색 route 결정
- 질문 범위 검사
- metadata filter 생성
- 후속 질문 처리를 위한 분석 정보 제공

### `src/rag/sql_tool.py`

MySQL에 저장된 정형 데이터를 조회하는 모듈입니다.

- 입학 정보 조회
- 교과목 조회
- 교수진 조회
- 사무실 연락처 조회
- KAIST 기본 정보 및 링크 조회

### `src/rag/vector_retriever.py`

Chroma VectorStore에서 문서를 검색하는 모듈입니다.

- OpenAI embedding 기반 유사도 검색
- 학과 및 문서 유형 기반 metadata filtering
- 검색 결과 부족 시 fallback 검색
- lightweight rerank 수행

### `src/rag/context_builder.py`

SQL 조회 결과와 Vector 검색 결과를 LLM 입력 context로 변환하는 모듈입니다.

- SQL 결과 Markdown table 변환
- Vector 문서 내용 정리
- 출처 정보 정리
- warning 메시지 구성
- context 길이 제한

### `src/rag/answer_generator.py`

검색 결과를 바탕으로 최종 답변을 생성하는 모듈입니다.

- system prompt 구성
- intent별 답변 지침 적용
- 출처 기반 답변 생성
- streaming 답변 생성 지원
- 개인별 합격 예측 질문 차단

### `src/rag/rag_pipeline.py`

RAG 전체 흐름을 연결하는 모듈입니다.

- 질문 분석
- 검색 실행
- context 생성
- LLM 답변 생성
- 결과 객체 반환
- Streamlit 연동용 streaming 실행

---

## 17. 테스트 및 평가

테스트 노트북과 평가 결과는 `notebooks/` 아래에서 관리됩니다.

```text
notebooks/rag_test.ipynb
notebooks/chatbot_eval_outputs/chatbot_test_results.csv
```

평가 파일은 예상 질문 100개에 대한 자동 평가 결과를 포함합니다.

| 평가 결과 | 개수 |
|---|---:|
| `PASS_ANSWER` | 47 |
| `PASS_DATA_MISSING` | 15 |
| `PASS_REJECT` | 7 |
| `PARTIAL_NO_DIRECT_EVIDENCE` | 6 |
| `FAIL_DATA_MISSING_OR_RETRIEVAL` | 19 |
| `FAIL_DATA_MISSING_NOT_DETECTED` | 3 |
| `FAIL_SHOULD_REJECT` | 3 |

평가 결과에는 질문 category, route, intent, SQL row 수, vector 검색 결과 수, fallback 여부, 출처 수, 응답 시간 등이 함께 저장됩니다.

---

## 18. 답변 정책

챗봇은 수집된 KAIST AI 관련 학과 자료를 기반으로 답변합니다.

다음과 같은 질문은 답변 범위에서 제외합니다.

```text
개인별 합격 가능성
합격 확률
내 학점이나 스펙 기반 합격 여부
수집되지 않은 학과에 대한 단정적 답변
KAIST AI 관련 학과와 무관한 일반 질문
```

허용되는 질문은 다음과 같습니다.

```text
입학 지원 자격
전형 절차
모집 일정
제출서류
교과목 및 커리큘럼
교수진 및 연구분야
학과 사무실 연락처
학과 소개
공식 홈페이지 및 자료 링크
```

---

## 19. 실행 흐름 요약

처음 실행하는 경우 다음 순서로 진행합니다.

```powershell
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 환경변수 설정
# 프로젝트 루트에 .env 파일 생성

# 3. 데이터 전처리
python data\preprocessing.py

# 4. MySQL 스키마 생성 및 데이터 적재
mysql -u root -p --local-infile=1 < sql\01_schema.sql
mysql -u root -p --local-infile=1 kaist_ai < sql\02_load.sql
mysql -u root -p --local-infile=1 kaist_ai < sql\03_verify.sql

# 5. VectorStore 생성
python data\build_vectorstore.py --reset --smoke-test

# 6. Streamlit 앱 실행
python -m streamlit run streamlit_app.py
```

---

## 20. 프로젝트 특징

이 프로젝트는 단순 문서 검색형 RAG가 아니라, 질문 유형에 따라 정형 데이터와 비정형 문서를 분리해서 활용하는 구조를 갖습니다.

- 교수진, 교과목, 연락처처럼 표 형태로 관리하기 좋은 정보는 MySQL에서 조회합니다.
- 모집요강, 학과 소개, 설명회 PDF처럼 문맥 기반 설명이 필요한 정보는 Chroma VectorStore에서 검색합니다.
- 두 정보가 함께 필요한 질문은 Hybrid 방식으로 SQL 결과와 Vector 문서를 함께 context에 넣습니다.
- 답변 생성 단계에서는 출처와 warning을 함께 제공해 사용자가 답변 근거를 확인할 수 있도록 구성했습니다.

