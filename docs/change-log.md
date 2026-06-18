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

### 변경 - 재수집 오류 감소와 AI College fallback 수집 개선
- 정적 HTML 수집에서 본문 텍스트에 적힌 `test.hwp`, `guide.pdf` 같은 파일명을 첨부 링크로 오인하지 않도록, HTML `href/src` 속성의 실제 파일 링크만 다운로드 후보로 사용하게 변경했다.
- `/file_down/`, `/download/`, `/downloads/`, `/attachment/` 계열 URL은 HTML 페이지 후보에서 제외했다.
- raw file policy를 HEAD/GET 요청 전에 먼저 적용하도록 변경해 `oldexam`, newsletter 등 제외 대상 파일에 불필요한 네트워크 요청을 하지 않게 했다.
- `file://` 같은 비 HTTP URL은 오류가 아니라 `unsupported_url_scheme` skip으로 기록하게 했다.
- Playwright 렌더링에서 `page.content()`가 navigation 중 오류를 내는 경우 body text 기반 synthetic HTML fallback을 시도하도록 보강했다.
- SPA route 렌더링 설정을 `commit`, 30초 timeout, 3초 후대기, 첫 route 실패 후 중단하지 않는 방식으로 조정했다.
- AI College는 headless 렌더링이 `wfrd.kaist.ac.kr/KA14.php`로 이동하는 경우가 있어, `spa_bundle_text`를 전처리 fallback 문서로 허용했다.
- JS literal 추출에서 Tailwind/class/template 문자열 노이즈를 더 강하게 제외했다.

### 이유
- 첨부파일명이 본문에 텍스트로만 등장하는 경우를 다운로드 링크로 오인해 403/404 raw 오류가 대량 발생했다.
- 수학과 old exam류 PDF는 이미 정책상 제외 대상인데, HEAD 실패 뒤 GET까지 진행되어 불필요한 오류가 생겼다.
- AI College는 headless browser에서 일부 route가 정상 DOM 렌더링되지 않아 0 chunk 상태였으므로, RAG 품질을 위해 bundle text fallback이 필요했다.

### 검증
```powershell
python -B -m unittest discover -s tests
python -m kaist_crawler raw --config configs\kaist_sources.yml --output data\kaist --clean
python -B -m kaist_crawler process --config configs\kaist_sources.yml --output data\kaist --clean
python -B -m kaist_crawler quality-gate --config configs\kaist_sources.yml --output data\kaist
```

결과:

```text
tests=35 OK
raw_files_written=697
raw_errors=14
documents=1247
chunks=2750
process_errors=5
filtered=2638
quality_status=warn
quality_score=60
kaist_ai_college chunks=26
kaist_mathsci status=warn chunks=1847
```

개선 전 재수집 로그는 `raw_errors=76`, `quality_status=fail`, `quality_score=30`, `kaist_ai_college chunks=0`이었다.

남은 품질 이슈:

- `kaist_mathsci`: PDF chunk 비율 85%, general content 비율 48%, PDF 텍스트 추출 오류 5건.
- 일부 SPA route는 headless 환경에서 여전히 navigation 오류가 있으나 bundle/PDF fallback으로 최소 수집은 가능하다.

### 변경 - 프로젝트 폴더 정리
- 현재 운영 데이터는 `data/kaist`만 사용하도록 폴더 구조를 정리했다.
- 이전 실험 산출물 `data/raw`, `data/processed`, `data/vector`, `data/natural_sciences`를 삭제하지 않고 `data/_archive_legacy` 아래로 이동했다.
- 재생성 가능한 캐시/임시 폴더 `.test_tmp`, `kaist_crawler/__pycache__`, `scripts/__pycache__`, `tests/__pycache__`를 삭제했다.
- README의 폴더 구조와 출력 구조를 현재 통합 저장 기준인 `data/kaist`에 맞게 수정했다.

### 이유
- AI 대학/자연과학대학 통합 이후 예전 분리 산출물이 같은 `data` 루트에 남아 있으면 어떤 데이터를 기준으로 전처리/벡터 저장해야 하는지 헷갈린다.
- 과거 산출물은 비교가 필요할 수 있어 바로 삭제하지 않고 archive로 보관했다.
- Python bytecode cache와 임시 테스트 폴더는 재생성 가능하므로 프로젝트 구조를 단순하게 만들기 위해 제거했다.

### 검증
```powershell
python -B -m unittest discover -s tests
python -B -m kaist_crawler quality-gate --config configs\kaist_sources.yml --output data\kaist
```

결과:

```text
tests=32 OK
quality_status=fail score=30
```

정리 후 구조:

```text
data/
  kaist/
  _archive_legacy/
```

### 변경 - config 기반 학과 metadata와 CLI 기본값 일반화
- `SourceConfig`에 `dept`, `dept_name` 필드를 추가하고 config 검증 대상에 포함했다.
- `source_scope_metadata`가 `institution`, `college`뿐 아니라 `dept`, `dept_name`도 전처리 문서 metadata에 주입하도록 변경했다.
- `rag_metadata.py`에서 `kaist_ai_college`, `kaist_main_kr`, `kaist_` prefix에 대한 기능 하드코딩을 제거했다.
- 문서의 학과 구분은 source id 특수 분기가 아니라 config의 `dept/dept_name`을 우선 사용하고, 없을 때만 `institution`/`college` prefix 기반 일반 fallback을 사용하도록 했다.
- `configs/kaist_sources.yml`, `configs/kaist_ai_sources.yml`, `configs/kaist_natural_sciences_sources.yml`의 각 source에 명시적인 `dept`, `dept_name`을 추가했다.
- CLI 기본 config/output/chunks 경로를 통합 기준인 `configs/kaist_sources.yml`, `data/kaist`, `data/kaist/processed/chunks.jsonl`로 변경했다.
- README의 vector build 예시 경로를 `data/kaist` 기준으로 수정했다.

### 이유
- 다른 대학원 사이트로 확장할 때 코드가 특정 KAIST source id를 보고 학과를 결정하면 metadata filter 품질이 흔들린다.
- source별 기관/단과대/학과 구분은 코드가 아니라 config가 책임지는 편이 재수집, 전처리, Chroma metadata filter까지 일관된다.
- 기본 CLI가 AI 전용 config를 바라보면 통합 수집 이후에도 실수로 일부 source만 처리할 수 있다.

### 검증
```powershell
python -m unittest discover -s tests
python -m compileall -q kaist_crawler tests
python -m kaist_crawler process --config configs\kaist_sources.yml --output data\kaist --clean
python -m kaist_crawler quality-gate --config configs\kaist_sources.yml --output data\kaist
```

결과:

```text
tests=32 OK
documents=942
chunks=2080
errors=4
filtered=2488
institution kaist=2080
college ai=185, natural_sciences=1895
dept aic=40, ai_systems=33, ax=18, fx=50, kaist=44, natsci=161, physics=193, mathsci=1243, chem=152, quantum=146
quality_status=fail score=30
```

남은 품질 이슈:

- `kaist_ai_college`: chunk 0개. SPA 렌더링/텍스트 추출 보강이 필요하다.
- `kaist_mathsci`: PDF chunk 비율 80%, PDF 텍스트 추출 오류 4건. 수학과 PDF 필터와 스캔 PDF 처리 정책을 더 다듬어야 한다.

### 변경 - KAIST 통합 저장 및 크롤링 전략
- AI 대학과 자연과학대학을 별도 프로젝트가 아니라 같은 KAIST 기관 아래의 단과대/학과 source group으로 보도록 통합했다.
- `SourceConfig`에 `institution`, `institution_name`, `college`, `college_name` 필드를 추가했다.
- `configs/kaist_ai_sources.yml`, `configs/kaist_natural_sciences_sources.yml`에 공통 `institution=kaist`와 단과대 구분용 `college=ai|natural_sciences`를 추가했다.
- AI 대학 6개 source와 자연과학대학 5개 source를 합친 통합 config `configs/kaist_sources.yml`를 추가했다.
- 기존 AI raw와 자연과학 raw를 `data/kaist/raw`로 합치고, manifest의 `raw_path`를 `data/kaist/raw/...` 기준으로 정규화했다.
- 전처리 단계에서 HTML, PDF, sheet row, SPA bundle text 문서 metadata에 기관/단과대 scope가 유지되도록 `source_scope_metadata`를 추가했다.
- 통합 운영 문서 `docs/kaist-unified-storage-and-crawl-strategy.md`를 추가했다.
- README의 기본 명령을 KAIST 통합 config와 `data/kaist` 출력 기준으로 갱신했다.

### 이유
- AI 대학과 자연과학대학은 모두 KAIST 내부 데이터이므로 저장 루트와 수집 정책의 상위 기준은 `kaist`로 같게 두는 편이 RAG 필터링과 확장에 유리하다.
- 단과대 차이는 별도 저장소가 아니라 metadata의 `college`로 구분해야 Chroma metadata filter에서 `institution=kaist`, `college=ai`, `college=natural_sciences` 같은 계층 검색이 가능하다.
- 다른 KAIST 단과대/학과를 추가할 때도 config만 합치고 같은 전처리/품질 평가/벡터 저장 흐름을 재사용할 수 있다.

### 검증
```powershell
python -m unittest tests.test_config tests.test_processor_metadata
python -m unittest discover -s tests
python -m py_compile kaist_crawler\models.py kaist_crawler\config.py kaist_crawler\processor.py tests\test_processor_metadata.py tests\test_config.py
python -m compileall -q kaist_crawler tests
python -m kaist_crawler process --config configs\kaist_sources.yml --output data\kaist --clean
python -m kaist_crawler quality-gate --config configs\kaist_sources.yml --output data\kaist
```

결과:

```text
targeted_tests=6 OK
all_tests=32 OK
configs/kaist_sources.yml sources=11
documents=942
chunks=2080
errors=4
filtered=2488
institution kaist=2080
college ai=185, natural_sciences=1895
quality_status=fail score=30
```

현재 Quality Gate 실패는 통합 구조 문제라기보다 `kaist_ai_college`가 chunk 0개로 남아 있는 문제 때문이다. 다음 작업에서 AI College SPA 렌더링/추출을 보강해야 한다.

### 변경
- URL 자동 수집 확장을 위해 `SiteProfile -> CrawlPlan -> QualityGate` 구조를 도입했다.
- `kaist_crawler/crawl_planner.py`를 추가해 사이트 구조 프로파일과 수집 계획 생성을 분리했다.
- `analyze-site` 출력에 `site_profile`, `crawl_plan`, `recommended_source`가 함께 포함되도록 변경했다.
- 분석 단계에서 query route를 보존하도록 개선했다. `index.php?mid=...`, `index.php?document_srl=...` 같은 게시판 URL이 수집 계획에 남는다.
- 링크 텍스트와 URL 관련도 기준으로 route 후보를 정렬하고, login/account/privacy/sitemap 계열 route를 제외하도록 개선했다.
- `kaist_crawler/quality_gate.py`를 추가해 전처리 결과의 벡터 저장 적합성을 자동 평가하도록 했다.
- `process` 명령이 `processed/quality_gate.json`, `processed/quality_gate.md`를 자동 생성하도록 했다.
- CLI에 `quality-gate` 명령을 추가했다.
- 구조 설명 문서 `docs/site-profile-crawl-plan-quality-gate.md`를 추가했다.

### 이유
- URL만 넣고 원하는 데이터를 자동 수집하려면 단순 adapter 선택보다 사이트 구조, URL 패턴, 파일 정책, 전처리 품질 판단이 분리되어야 한다.
- 자연과학대학 실험에서 query route, extensionless route, PDF viewer, 과거 시험 PDF, metadata 오분류 문제가 확인됐다.
- 벡터 저장 전 품질 판단을 자동화해야 다른 대학원 사이트를 반복적으로 추가할 수 있다.

### 검증
```powershell
python -m unittest tests.test_site_analyzer tests.test_quality_gate
python -m unittest discover -s tests
python -m kaist_crawler quality-gate --config configs\kaist_natural_sciences_sources.yml --output data\natural_sciences
python -m kaist_crawler analyze-site --help
python -m kaist_crawler quality-gate --help
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --clean
```

결과:

```text
tests=30 OK
natural_sciences quality_status=warn score=71
kaist_ai documents=134 chunks=185 errors=0 filtered=911
kaist_ai quality_status=fail score=30
configs/kaist_natural_sciences_sources.yml sources=5
```

KAIST AI의 Quality Gate 실패는 `kaist_ai_college`가 현재 chunk 0개인 상태를 잡아낸 결과이다.

### 남은 이슈
- Quality Gate는 아직 규칙 기반이다. `content_subtype`과 chunk별 `vector_candidate`가 추가되면 더 정확해진다.
- CrawlPlan의 route/file policy를 adapter가 모두 읽는 구조는 아직 아니다. 현재는 일부 정책은 config와 보고서에 기록되고, 일부는 adapter에 직접 반영되어 있다.

## 2026-06-17

### 변경
- 자연과학대학 계열 5개 사이트를 `analyze-site`로 분류하고, 별도 수집 config `configs/kaist_natural_sciences_sources.yml`를 생성했다.
- 자연과학대학 수집 결과를 `data/natural_sciences` 아래에 저장하고 전처리까지 실행했다.
- 정적 HTML adapter가 확장자 없는 링크(`/faculty`, `/notice` 등)를 따라가도록 개선했다.
- 정적 HTML adapter가 `index.php?mid=...`, `index.php?document_srl=...` 같은 query 기반 페이지를 따라가도록 개선했다.
- `javascript` pseudo-link와 `/@facebook` 같은 SNS pseudo-link를 HTML page 후보에서 제외하도록 개선했다.
- 새 source가 기존 AI 학과 keyword에 의해 `aic`, `ax`, `fx`로 오분류되지 않도록 source id 기반 `dept` 기본값을 추가했다.
- 사이트 분석기의 첨부파일 후보 필터를 강화해 JS 코드 조각이 `.doc` 파일로 오탐되는 문제를 줄였다.
- 자연과학대학 수집 품질 평가 문서 `docs/natural-sciences-crawl-quality.md`를 추가했다.

### 이유
- 물리학과 사이트는 query 기반 라우팅이라 기존 정적 HTML adapter가 root 한 페이지만 수집했다.
- 자연과학 사이트는 `dept`가 없는 상태에서 본문 keyword로 AI 학과에 오분류되어 metadata filter 검색 품질을 떨어뜨릴 수 있었다.
- 분석기 추천 config를 실제 사이트에 적용해 보면서 다른 대학원 확장 시 필요한 crawler 보강점을 검증하기 위해서다.

### 실행
```powershell
python -m kaist_crawler analyze-site https://natsci.kaist.ac.kr --id kaist_natsci --name "KAIST College of Natural Sciences" --output configs\analysis_kaist_natsci.yml
python -m kaist_crawler analyze-site https://physics.kaist.ac.kr --id kaist_physics --name "KAIST Department of Physics" --output configs\analysis_kaist_physics.yml
python -m kaist_crawler analyze-site https://mathsci.kaist.ac.kr/home/ --id kaist_mathsci --name "KAIST Department of Mathematical Sciences" --output configs\analysis_kaist_mathsci.yml
python -m kaist_crawler analyze-site https://chem.kaist.ac.kr/main/ --id kaist_chem --name "KAIST Department of Chemistry" --output configs\analysis_kaist_chem.yml
python -m kaist_crawler analyze-site https://quantum.kaist.ac.kr/ --id kaist_quantum --name "KAIST Graduate School of Quantum Science and Technology" --output configs\analysis_kaist_quantum.yml
python -m kaist_crawler raw --config configs\kaist_natural_sciences_sources.yml --output data\natural_sciences --clean
python -m kaist_crawler raw --config configs\kaist_natural_sciences_sources.yml --output data\natural_sciences --source kaist_physics
python -m kaist_crawler process --config configs\kaist_natural_sciences_sources.yml --output data\natural_sciences --clean
```

### 결과
```text
raw unique=491
documents=808
chunks=1895
errors=7
filtered=1574
```

chunk site 분포:

```text
kaist_mathsci=1243
kaist_physics=193
kaist_natsci=161
kaist_chem=152
kaist_quantum=146
```

chunk source type:

```text
html=896
pdf=999
```

chunk dept:

```text
natsci=161
physics=193
mathsci=1243
chem=152
quantum=146
```

### 평가
- 화학과, 양자대학원, 물리학과는 교수진/입학/교과목/연구/공지 HTML 품질이 양호하다.
- 수리과학과는 수집량은 많지만 PDF가 과도하게 많고, 과거 시험/이미지 기반 PDF가 섞여 벡터 저장 전 필터링이 필요하다.
- 자연과학대학 본부는 학과 소개와 연구사업 정보는 유용하지만, 오시는 길/연구비 통계/일반 표 데이터는 RAG 목적에 따라 제외 후보이다.

### 남은 이슈
- PDF viewer URL의 `file=` 파라미터에서 실제 PDF URL을 추출하면 수리과학과 PDF 수집 오류가 줄어든다.
- `research_highlight`, `notice`, `seminar`, `old_exam` 같은 content subtype을 추가하면 자연과학 사이트의 RAG 품질 평가가 더 쉬워진다.

## 2026-06-17

### 변경
- 새 대학원 URL을 분석해 수집 config 초안을 추천하는 `kaist_crawler/site_analyzer.py`를 추가했다.
- CLI에 `python -m kaist_crawler analyze-site <url>` 명령을 추가했다.
- 분석기는 정적 HTML, SPA, SPA+Google Sheets 구조를 구분하고 `adapter`, `routes`, `known_files`, `robots_url`, `sitemap_status`, `raw` 옵션 초안을 추천한다.
- `tests/test_site_analyzer.py`를 추가해 정적 HTML 사이트와 SPA+Google Sheets 사이트의 추천 결과를 검증했다.
- README에 사이트 분석기 사용법과 새 모듈 역할을 추가했다.

### 이유
- 다른 대학원 사이트로 확장하기 전에 바로 수집을 실행하면 사이트 구조 차이 때문에 raw 데이터 품질이 흔들릴 수 있다.
- 먼저 사이트 구조를 분석하고 config 초안을 사람이 검토한 뒤 수집하면, 전처리 개선이 KAIST 구조에만 과적합되는 위험을 줄일 수 있다.
- 분석기 출력의 `recommended_source`를 `configs/kaist_ai_sources.yml`에 붙여 넣는 방식이면 기존 raw/process/vector 명령 흐름을 유지할 수 있다.

### 사용
```powershell
python -m kaist_crawler analyze-site https://example.edu/graduate --id example_graduate --name "Example Graduate School" --output configs\recommended_example.yml
```

### 검증
```powershell
python -m py_compile kaist_crawler\site_analyzer.py kaist_crawler\cli.py tests\test_site_analyzer.py
python -m unittest tests.test_site_analyzer
python -m unittest discover -s tests
python -m kaist_crawler analyze-site --help
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --clean
```

결과:

```text
test_site_analyzer=2 OK
tests=23 OK
analyze-site help OK
documents=134 chunks=185 errors=0 filtered=911
```

### 남은 이슈
- Google Sheets를 사용하는 사이트는 spreadsheet id까지만 자동 감지하고, sheet 이름과 row mapping은 아직 사람이 채워야 한다.
- 분석기는 config 추천기이며, 추천 결과를 검토 없이 바로 대규모 크롤링하는 용도는 아니다.

## 2026-06-17

### 변경
- Google Sheets row 매핑 로직을 `kaist_crawler/processor.py`에서 `kaist_crawler/sheet_mapping.py`로 분리했다.
- `processor.py`의 기존 `add_sheet_row_documents` 함수는 유지하되, 내부에서 새 `sheet_row_documents` 변환 함수를 호출하도록 바꿨다.

### 이유
- `processor.py`가 raw manifest 순회, HTML/PDF 처리, sheet row 매핑까지 모두 담당하고 있어 다른 대학원 사이트의 sheet/API 구조를 추가할 때 수정 범위가 커질 수 있었다.
- sheet row 매핑을 독립 모듈로 분리하면 Google Sheets, Airtable, JSON API 같은 정형 데이터 매핑 규칙을 processor와 분리해서 테스트하고 확장할 수 있다.
- 기존 함수명은 유지해서 현재 테스트와 호출부가 바로 깨지지 않게 했다.

### 검증
```powershell
python -m py_compile kaist_crawler\processor.py kaist_crawler\sheet_mapping.py tests\test_sheet_mapping.py
python -m unittest tests.test_sheet_mapping
python -m unittest discover -s tests
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --clean
```

결과:

```text
test_sheet_mapping=5 OK
tests=21 OK
documents=134 chunks=185 errors=0 filtered=911
```

### 변경
- RAG용 metadata 정규화 모듈 `kaist_crawler/rag_metadata.py`를 추가했다.
- 모든 전처리 문서/chunk에 `dept`, `dept_name`, `content_type`, `source_type`, `section`, `page` metadata가 들어가도록 보강했다.
- HTML은 heading 기반 section 단위로 분리하고, PDF는 page 단위로 텍스트를 보존하도록 변경했다.
- PDF page 기반 전처리에서 짧지만 중요한 슬라이드가 과도하게 제거되지 않도록 `pdf` 최소 길이 기준을 `300`자에서 `80`자로 낮췄다.
- `faculty`, `news`, `html`, `pdf`를 RAG 검색 의도에 맞춰 `person`, `admission`, `event`, `course`, `scholarship`, `department_profile` 등으로 재분류하도록 했다.
- Chroma 검색에서 질문 기반 metadata filter를 먼저 적용하고, 결과가 부족하면 `department_only`, `content_type_only`, `no_filter`로 fallback하는 `kaist_crawler/retrieval.py`를 추가했다.
- `scripts/retrieval_smoke_test.py`가 기본적으로 metadata filter 검색을 사용하도록 바꿨고, `--no-metadata-filter` 옵션을 추가했다.
- OpenAI embedding 빌드 시 `.env`의 `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_EMBEDDING_MODEL`을 자동 로드하도록 보강했다.
- `tests/test_rag_metadata.py`를 추가해 metadata 정규화, section chunking, retrieval filter plan을 검증했다.

### 이유
- 기존 chunk는 `html/pdf/news/faculty` 중심이라 질문 의도인 입학, 교수진, 교과목, 장학금, 행사와 직접 연결되지 않았다.
- retrieval 테스트에서 관련 문서가 있어도 다른 학과나 KAIST 공통 페이지가 먼저 올라오는 문제가 있었으므로, 전처리 metadata와 Chroma filter 검색을 함께 개선했다.
- PDF를 page 단위로 나누면 출처 page를 보존할 수 있지만, 300자 기준에서는 핵심 슬라이드가 사라져 AX 입시설명회 검색 품질이 낮아졌다.

### 실행
```powershell
python -m unittest discover -s tests
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --clean
python -m kaist_crawler build-vector --input data\processed\chunks.jsonl --output data --embedding-provider openai
python scripts\retrieval_smoke_test.py --top-k 5
```

결과:

```text
tests=20 OK
documents=134
chunks=185
errors=0
filtered=911
Chroma collection=graduate_rag_openai_text-embedding-3-small_1536
Chroma count=185
```

chunk `content_type` 분포:

```text
admission=68
person=47
event=33
scholarship=12
course=10
department_profile=10
general=3
office_contact=2
```

chunk `dept` 분포:

```text
fx=50
kaist=44
aic=40
ai_systems=33
ax=18
```

### 평가
- `AI미래학과 교수진은?`은 `dept=fx`, `content_type=person` strict filter로 FX faculty 문서만 반환한다.
- `AX 학과 입시설명회 내용 요약해줘`는 `dept=ax`, `content_type=admission` strict filter로 AX 입시설명회 PDF page가 top 결과에 나온다.
- `KAIST 대학원 장학금이나 등록 관련 정보는?`은 `content_type=scholarship` filter로 KAIST 등록/장학 페이지를 우선 검색한다.
- KAIST 본원 공통 내비게이션에 포함된 AI 학과명이 본원 문서를 특정 학과로 오분류하던 문제를 막기 위해 `kaist_main_kr`은 기본 `dept=kaist`로 고정했다.

### 남은 이슈
- AI College SPA는 여전히 실제 rendered content 수집이 부족해 `AI College 교육과정` 질문이 AIC PDF 중심으로 검색된다.
- `AI Systems 대학원 입학 지원 조건`은 strict filter는 잘 작동하지만, PDF/HTML 중 대학원 지원 조건 page를 더 위로 올리려면 다음 단계에서 reranker가 필요하다.
- KAIST 본원 HTML에는 아직 공통 내비게이션 boilerplate가 일부 남아 있어 본문 정제 개선 여지가 있다.

## 2026-06-17

### 변경
- 대표 질문으로 Chroma retrieval 품질을 확인하는 `scripts/retrieval_smoke_test.py`를 추가했다.
- 스크립트를 직접 실행해도 로컬 `kaist_crawler` 패키지를 import할 수 있도록 프로젝트 루트를 `sys.path`에 추가했다.

### 이유
- 벡터스토어 생성 여부만으로는 RAG 품질을 판단할 수 없어서, 실제 사용자가 물어볼 만한 질문으로 top-k 검색 결과를 점검할 필요가 있다.
- PowerShell here-string으로 한국어 질의를 넘기면 터미널 인코딩에 따라 질의가 깨질 수 있으므로, UTF-8 소스 파일 안에 대표 질문을 고정해 재현 가능한 smoke test로 만들었다.

### 실행
```powershell
python scripts\retrieval_smoke_test.py --top-k 5
```

결과:

```text
collection=graduate_rag_openai_text-embedding-3-small_1536
count=147
embedding_provider=openai
embedding_model=text-embedding-3-small
embedding_dimensions=1536
```

### 평가
- AI Systems 입학 질문은 관련 PDF와 입학 안내 HTML이 top-2로 검색되어 품질이 좋다.
- KAIST 장학금/등록 질문은 KAIST 등록 FAQ와 장학 정책 문서가 top-2로 검색되어 품질이 좋지만, 일부 KAIST 공통 내비게이션 텍스트가 섞인다.
- AX 입시설명회 질문은 AX PDF가 검색되지만 top-4로 밀려나고 FX/AI Systems의 통합 입시설명회 문서가 먼저 나온다. 학과명 기반 site boost 또는 metadata filter가 필요하다.
- AI미래학과 교수진 질문은 FX faculty 문서가 검색되지만 top-3부터 나오고 KAIST 공통 학사 페이지가 앞에 나온다. document_type=faculty 또는 site=kaist_fx boost가 필요하다.
- AI College 학과/교육과정 질문은 정확한 AI College 문서가 부족하고 KAIST 공통 페이지가 먼저 나온다. AI College SPA rendered HTML 수집 또는 안전한 bundle text 정제가 필요하다.
- 학과명을 더 명시한 추가 질의에서는 AIC/AX/FX 관련 문서가 검색 결과에 들어오므로, 데이터 부재보다는 현재 retrieval 단계의 site/document_type routing 부족이 더 큰 문제로 보인다.

### 다음 작업 후보
- 질의에 학과/사이트명이 들어오면 해당 `site`와 `document_type`을 boost/filter하는 retrieval policy를 추가한다.
- KAIST 본원 HTML의 공통 내비게이션/학과 목록 boilerplate 제거를 강화한다.
- AI College rendered HTML 수집 실패 문제를 해결하거나, bundle text에서 라우트별 실제 콘텐츠만 추출하는 fallback을 만든다.

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

- 전처리된 `data/processed/chunks.jsonl` 147개 chunk로 OpenAI embedding 기반 Chroma vector store를 생성했다.
- `.env`의 `OPENAI_EMBEDDING_MODEL` 설정에 따라 `text-embedding-3-small` 모델이 사용됐다.

### 실행

```powershell
python -m kaist_crawler build-vector --input data\processed\chunks.jsonl --output data --embedding-provider openai
```

결과:

```text
chunks=147
vector_output=C:\Users\Playdata\workspace\kaist_ai_crawler_project\data\vector
```

### 검증

```text
data/vector/simple/chunks.jsonl: 147 lines
data/vector/chroma: exists
Chroma collection: graduate_rag_openai_text-embedding-3-small_1536
Collection count: 147
```

### 메모

- 첫 실행은 네트워크 제한 때문에 실패했고, 승인된 네트워크 실행으로 OpenAI embedding API 호출에 성공했다.
- 다음 단계는 대표 질문으로 Chroma 검색 smoke test를 수행해 retrieval 품질을 확인하는 것이다.

## 2026-06-17

### 변경

- 기능적으로 KAIST/FX 사이트 구조에 묶여 있던 하드코딩을 설정 기반으로 일반화했다.
- `FxSheetsSpaAdapter`의 dynamic route 생성을 `source.dynamic_routes` 설정 기반으로 변경했다.
- sheet row에서 첨부 파일 링크를 찾는 로직을 `news` sheet 전용에서 모든 sheet row 값 스캔 방식으로 변경했다.
- `processor.py`의 `news`/`faculty` 전용 row 문서 생성 로직을 `google_sheets.document_mappings` 기반으로 변경했다.
- FX의 기존 `news`, `faculty` row 문서 생성 규칙을 `configs/kaist_ai_sources.yml`로 이동했다.
- 기본 전처리 필터에서 `google_sheet`, `spa_bundle_text` 문서를 vector 후보에서 제외하도록 했다.
- 기본 file policy에서 KAIST 전용 `kaistian` 패턴을 제거했다.
- 기본 Chroma collection prefix를 `kaist_ai`에서 `graduate_rag`로 변경했다.
- 기본 User-Agent를 `KAIST-AI-RAG-Crawler`에서 `Graduate-RAG-Crawler`로 변경했다.
- CLI description을 `Graduate school RAG crawler`로 일반화했다.
- `tests/test_sheet_mapping.py`를 추가했다.

### 이유

- 변수명이나 파일명은 KAIST 중심이어도 되지만, 기능이 특정 사이트의 `news/faculty` schema에 묶이면 다른 대학원 사이트를 추가할 때 RAG 품질이 흔들린다.
- Google Sheets, Airtable, JSON API 같은 구조화 데이터는 학교마다 field 이름이 다르므로 row mapping을 YAML 설정으로 옮기는 편이 안전하다.
- SPA bundle text와 sheet 원본 전체 문서는 다른 사이트에서도 중복/노이즈가 될 가능성이 높아 기본 vector 후보에서 제외했다.

### 영향 파일

- `kaist_crawler/adapters.py`
- `kaist_crawler/processor.py`
- `kaist_crawler/vector_store.py`
- `kaist_crawler/http_client.py`
- `kaist_crawler/cli.py`
- `configs/kaist_ai_sources.yml`
- `tests/test_sheet_mapping.py`
- `README.md`
- `docs/kaist-crawling-strategy.md`

### 검증

```powershell
python -m py_compile kaist_crawler\__main__.py kaist_crawler\__init__.py kaist_crawler\models.py kaist_crawler\config.py kaist_crawler\http_client.py kaist_crawler\store.py kaist_crawler\extractors.py kaist_crawler\rendering.py kaist_crawler\policies.py kaist_crawler\processor.py kaist_crawler\vector_store.py kaist_crawler\adapters.py kaist_crawler\pipeline.py kaist_crawler\cli.py tests\test_config.py tests\test_policies.py tests\test_sheet_mapping.py
python -m unittest discover -s tests
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --clean
```

결과:

```text
14 tests OK
documents=49 chunks=147 errors=0 filtered=139
```

문서 타입:

```text
pdf=4
html=13
news=9
faculty=23
```

chunk 타입:

```text
pdf=40
html=57
news=20
faculty=30
```

### 평가

- 이전 전처리 결과의 주요 노이즈였던 `google_sheet` 전체 문서와 `spa_bundle_text`가 vector 후보에서 제외됐다.
- chunk 수가 `289`에서 `147`로 줄었고, 남은 chunk는 PDF/HTML/news/faculty 중심이 됐다.
- 다른 사이트에서는 `google_sheets.document_mappings`만 추가하면 코드 수정 없이 sheet row 문서를 만들 수 있다.

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

### 설정과 구현 불일치

- `dynamic_routes`는 Google Sheets 기반 route 생성에 사용되지만, `route_aliases` 설정은 아직 실제 수집/전처리 로직에 사용되지 않는다.

### SPA 렌더링 환경 문제

- 현재 실행 환경에서는 Playwright가 권한 문제로 실패한다.
- 이 상태에서는 SPA route rendered HTML 대신 shell fallback과 bundle text 의존도가 커진다.

## 다음 작업 후보

1. 전처리 개선
   - 문서 타입별 chunk 전략 분리
   - `rag_category` metadata 추가

2. 벡터 저장
   - 전처리 개선 후 OpenAI embedding으로 Chroma vector store 생성

3. 확장 준비
   - `route_aliases`를 실제 URL canonicalization 또는 metadata에 반영할지 결정
   - 패키지명과 기본 config 이름을 장기적으로 일반화할지 결정
