# 변경 기록

이 문서는 크롤러 프로젝트에서 만든 기능, 개선, 리팩토링, 검증 결과, 남은 이슈를 날짜별로 기록한다.

앞으로 코드, 설정, 전처리 정책, 벡터 저장 전략을 변경하면 이 파일에도 함께 기록한다.

## 기록 규칙

- 날짜는 변경한 날짜 기준으로 쓴다.
- 변경한 내용뿐 아니라 왜 바꿨는지도 적는다.
- 검증한 명령과 결과를 남긴다.
- 아직 해결하지 않은 리스크나 다음 작업을 함께 남긴다.
- raw/processed/vector 산출물 개수가 바뀌면 핵심 숫자를 기록한다.

## 2026-06-17

### 변경

- `docs/change-log.md`를 새로 추가했다.
- 지금까지 만든 크롤링, 전처리, 벡터 저장, 리팩토링 변경 사항을 한곳에 기록하기 시작했다.

### 이유

- 프로젝트가 크롤링, 전처리, 벡터 저장, 정책 설정으로 나뉘면서 변경 이유를 추적할 필요가 생겼다.
- 이후 다른 대학원 사이트로 확장할 때 어떤 정책이 왜 들어갔는지 확인할 수 있어야 한다.

### 검증

- 문서 추가 작업이므로 별도 코드 실행은 하지 않았다.

## 2026-06-17

### 변경

- 설정 로딩을 `CrawlerConfig` 중심으로 리팩토링했다.
- `configs/kaist_ai_sources.yml`의 `request_timeout_seconds`, `polite_delay_seconds`가 실제 HTTP client에 적용되도록 했다.
- 설정 검증을 추가했다.
  - source id 중복 검증
  - 지원하지 않는 adapter 검증
  - 주요 YAML 키 오타 검증
  - 주요 필드 타입 검증
- `polite_delay_seconds` 기본값을 `1`초에서 `0.2`초로 낮췄다.
- 전처리 필터 실행 함수 `filter_documents`, `filter_chunks`, `filter_event`를 `processor.py`에서 `policies.py`로 옮겼다.
- `tests/test_config.py`, `tests/test_policies.py`를 추가했다.
- `.test_tmp/`를 `.gitignore`에 추가했다.

### 이유

- 다른 대학원 사이트를 추가할 때 YAML 오타나 잘못된 adapter를 초기에 잡기 위해서다.
- 기존에는 timeout/delay 설정이 YAML에는 있었지만 실제 수집에 적용되지 않았다.
- `processor.py`가 문서 생성과 필터 실행을 모두 담당해 커지고 있었기 때문에 필터 책임을 policy 모듈로 분리했다.
- 정책 변경이 RAG 품질에 직접 영향을 주기 때문에 최소 단위 테스트가 필요했다.

### 영향 파일

- `kaist_crawler/config.py`
- `kaist_crawler/http_client.py`
- `kaist_crawler/pipeline.py`
- `kaist_crawler/policies.py`
- `kaist_crawler/processor.py`
- `configs/kaist_ai_sources.yml`
- `tests/test_config.py`
- `tests/test_policies.py`
- `.gitignore`

### 검증

```powershell
python -m py_compile kaist_crawler\__main__.py kaist_crawler\__init__.py kaist_crawler\models.py kaist_crawler\config.py kaist_crawler\http_client.py kaist_crawler\store.py kaist_crawler\extractors.py kaist_crawler\rendering.py kaist_crawler\policies.py kaist_crawler\processor.py kaist_crawler\vector_store.py kaist_crawler\adapters.py kaist_crawler\pipeline.py kaist_crawler\cli.py tests\test_config.py tests\test_policies.py
python -m unittest discover -s tests
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --clean
```

결과:

```text
10 tests OK
documents=55 chunks=289 errors=0 filtered=162
```

이후 raw 재수집 후 다시 전처리했을 때 결과:

```text
documents=55 chunks=289 errors=0 filtered=136
```

## 2026-06-17

### 변경

- raw 수집을 다시 실행했다.

```powershell
python -m kaist_crawler raw --config configs\kaist_ai_sources.yml --output data --clean
```

결과:

```text
raw_files_written=169
errors=5
```

사이트별 raw manifest/skipped 개수:

```text
kaist_ai_college: manifest=13 skipped=0
kaist_ai_systems: manifest=5 skipped=0
kaist_aic: manifest=13 skipped=0
kaist_ax: manifest=13 skipped=0
kaist_fx: manifest=45 skipped=0
kaist_main_kr: manifest=80 skipped=26
```

### 평가

- `kaist_main_kr`의 뉴스레터류 파일 26개가 raw file policy에 의해 다운로드되지 않고 `skipped_files.jsonl`에 기록됐다.
- Playwright 실행 권한 문제로 SPA route 렌더링은 실패했고, shell fallback 중심으로 저장됐다.

### 남은 이슈

- 현재 환경에서 Playwright가 `PermissionError: [WinError 5] 액세스가 거부되었습니다`로 실패한다.
- SPA 사이트의 route별 rendered HTML 품질을 확보하려면 Playwright 실행 권한 문제를 해결해야 한다.

## 2026-06-17

### 변경

- 전처리를 다시 실행하고 데이터 품질을 평가했다.

```powershell
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --clean
```

결과:

```text
documents=55
chunks=289
errors=0
filtered=136
```

문서 분포:

```text
by_site:
  kaist_aic: 3
  kaist_ai_systems: 5
  kaist_ax: 2
  kaist_fx: 35
  kaist_main_kr: 9
  kaist_ai_college: 1

by_type:
  pdf: 4
  html: 13
  google_sheet: 2
  news: 9
  faculty: 23
  spa_bundle_text: 4
```

chunk 분포:

```text
chunks=289
pdf=40
html=57
google_sheet=44
news=19
faculty=28
spa_bundle_text=101
```

### 평가

- 핵심 PDF 4개와 AI Systems 정적 HTML은 벡터화 후보로 적합하다.
- KAIST 본원 뉴스레터 PDF는 raw 단계에서 잘 제외됐다.
- `errors.jsonl`은 비어 있어 전처리 실패는 없었다.
- `spa_bundle_text`가 101 chunks로 많고, React/router 오류 문자열, CSS class, minified JS 조각이 섞여 있어 RAG 품질을 낮출 가능성이 크다.
- FX `google_sheet` 전체 문서가 44 chunks이고, row 단위 `news`/`faculty` 문서와 중복될 가능성이 크다.
- 현재 chunks 289개 중 약 145개가 노이즈 또는 중복 위험이 있는 데이터로 평가됐다.

### 다음 개선 후보

- `google_sheet` 전체 문서는 기본적으로 vector 후보에서 제외하고 row 단위 문서만 사용한다.
- `spa_bundle_text`는 기본 제외하거나, framework/CSS/minified JS 문자열을 강하게 정제한 뒤 fallback 용도로만 사용한다.
- KAIST 본원 HTML 중 일반 학사행정 페이지를 더 줄이고 입학/대학원 관련 페이지 중심으로 제한한다.
- 뉴스 문서는 admission/event/notice/research/press 같은 category를 붙여 포함 여부를 조절한다.

## 2026-06-16

### 변경

- Python 패키지 `kaist_crawler` 기반 프로젝트 구조를 만들었다.
- raw 수집, 전처리, 벡터 저장을 명령어로 분리했다.

명령어:

```powershell
python -m kaist_crawler raw
python -m kaist_crawler process
python -m kaist_crawler run
python -m kaist_crawler build-vector
```

- 수집 대상 6개 사이트를 `configs/kaist_ai_sources.yml`에 정의했다.
  - `https://aic.kaist.ac.kr/`
  - `https://ai-systems.kaist.ac.kr/`
  - `https://ax.kaist.ac.kr/`
  - `https://fx.kaist.ac.kr/`
  - `https://www.kaist.ac.kr/kr/`
  - `https://aicollege.kaist.ac.kr/`

### 이유

- raw 수집과 전처리를 분리해, 비싼 크롤링을 다시 하지 않고 전처리/임베딩 전략을 반복 실험하기 위해서다.
- 사이트 구조가 정적 HTML, Vite/React SPA, Google Sheets 기반 SPA로 나뉘어 하나의 generic crawler보다 adapter 분리가 안정적이라고 판단했다.

### 구현

- `StaticHtmlAdapter`: 정적 HTML 페이지와 같은 origin link 수집
- `ViteReactSpaAdapter`: SPA root HTML, asset, route shell/rendered HTML, 파일 링크 수집
- `FxSheetsSpaAdapter`: SPA 수집에 Google Sheets gviz JSON 수집 추가
- `RawStore`: raw 파일 저장과 `manifest.jsonl` 기록
- `processor.py`: raw manifest 기반 문서 생성, PDF 텍스트 추출, chunk 생성
- `vector_store.py`: hash/OpenAI embedding, simple JSONL vector, Chroma 저장

## 2026-06-16

### 변경

- raw 명령은 진짜 raw 저장만 하도록 정리했다.
- PDF 텍스트 추출을 raw 단계에서 제거하고 process 단계로 옮겼다.
- SPA route 수집에 Playwright 렌더링을 추가했다.
- PDF 텍스트 추출 순서를 정했다.
  1. `pymupdf`
  2. `pdfplumber`
  3. `pypdf`
  4. `PyPDF2`

### 이유

- raw는 원본 보존과 재현성이 중요하다.
- PDF 텍스트 추출과 노이즈 제거는 여러 번 실험할 수 있어야 하므로 전처리 단계가 더 적절하다.

## 2026-06-16

### 변경

- raw file policy를 추가했다.
- `HEAD` 요청으로 파일 크기와 content-type을 먼저 확인한 뒤 다운로드 여부를 판단하게 했다.
- 다운로드하지 않은 파일은 `raw/<site>/skipped_files.jsonl`에 기록하게 했다.
- 전처리 필터 정책을 추가했다.
  - 중복 raw sha256 제외
  - 중복 문서 텍스트 제외
  - 중복 chunk 제외
  - 너무 짧은 문서 제외
  - HTML shell 제외
  - 대용량/뉴스레터 PDF 제외
  - vendor 성격 asset 제외
- 전처리에서 제외된 항목은 `processed/filtered.jsonl`에 기록하게 했다.

### 이유

- KAIST 본원 뉴스레터 PDF처럼 크고 RAG 기여도가 낮은 파일이 raw 수집 시간을 크게 늘렸다.
- 벡터 저장 후보에서 제외한 이유를 추적할 수 있어야 이후 품질 평가가 가능하다.

## 2026-06-16

### 변경

- OpenAI embedding 기반 vector store 생성을 지원했다.
- 기본 OpenAI embedding 모델을 `text-embedding-3-large`로 설정했다.
- 비용/속도 조절을 위해 `--embedding-model`, `--embedding-dimensions`, `--embedding-batch-size`, `--collection` 옵션을 추가했다.
- Chroma 저장과 simple JSONL embedding 저장을 함께 지원했다.

### 이유

- 최종 목표가 RAG 챗봇용 vector store 생성이므로, local hash embedding은 테스트용으로 두고 실제 품질 평가는 OpenAI embedding으로 진행하기 위해서다.

## 현재 남은 구조적 이슈

### FX 전용 하드코딩

- `FxSheetsSpaAdapter`는 `news`, `faculty`, `/news/{slug}`, `/faculty-card/{slug}`를 코드에 직접 사용한다.
- `processor.py`도 `title_ko`, `title_en`, `body_ko`, `body_en`, `name_ko`, `name_en`을 고정 사용한다.
- 다른 대학원 사이트의 sheet/API 구조로 확장하려면 설정 기반 row mapping이 필요하다.

### 설정과 구현 불일치

- `dynamic_routes`와 `route_aliases` 설정은 일부 존재하지만 아직 일반화된 방식으로 충분히 사용되지 않는다.

### KAIST 전용 기본값

- 기본 file policy에 `kaistian` 패턴이 들어 있다.
- `vector_store.py`의 기본 collection 이름 prefix가 `kaist_ai`다.
- HTTP User-Agent가 `KAIST-AI-RAG-Crawler`다.
- CLI description이 `KAIST College of AI crawler`다.

### SPA 렌더링 환경 문제

- 현재 실행 환경에서는 Playwright가 권한 문제로 실패한다.
- 이 상태에서는 SPA route rendered HTML 대신 shell fallback과 bundle text 의존도가 커진다.

## 다음 작업 후보

1. 전처리 개선
   - `google_sheet` 전체 문서 제외
   - `spa_bundle_text` 기본 제외 또는 강한 정제
   - 문서 타입별 chunk 전략 분리
   - `rag_category` metadata 추가

2. FX 전용 처리 일반화
   - sheet/API row mapping을 YAML 설정으로 이동
   - dynamic route 생성을 설정 기반으로 변경

3. 벡터 저장
   - 전처리 개선 후 OpenAI embedding으로 Chroma vector store 생성

4. 확장 준비
   - `kaistian`, collection prefix, User-Agent, CLI description 일반화
