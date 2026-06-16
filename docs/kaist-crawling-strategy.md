# KAIST AI 대학원 크롤링 전략

마지막 갱신일: 2026-06-16

## 목표

대학원 URL 또는 source 설정을 기준으로 다음 흐름을 자동화한다.

1. 공개 페이지와 첨부 파일을 raw data로 저장한다.
2. PDF 같은 다운로드 자료는 실제 파일 응답인지 검증한 뒤 원본 파일로 저장한다.
3. 전처리 단계에서 HTML, SPA 렌더링 DOM, JavaScript bundle, Google Sheets JSON, PDF에서 텍스트를 추출한다.
4. 추출 문서를 chunk로 나눈다.
5. chunk를 기반으로 RAG용 vector store를 생성한다.

현재 수집 대상은 6개 사이트다.

- `https://aic.kaist.ac.kr/`
- `https://ai-systems.kaist.ac.kr/`
- `https://ax.kaist.ac.kr/`
- `https://fx.kaist.ac.kr/`
- `https://www.kaist.ac.kr/kr/`
- `https://aicollege.kaist.ac.kr/`

## 핵심 판단

모든 사이트에 하나의 generic crawler를 적용하지 않는다. KAIST AI 관련 사이트들은 정적 HTML, Vite/React SPA, Google Sheets 기반 데이터 로딩이 섞여 있어서 사이트 구조별 adapter를 나누는 방식이 더 안정적이다.

파이프라인은 다음처럼 책임을 분리한다.

```text
raw 수집
  -> raw manifest 기반 전처리
  -> vector store 생성
```

- `adapters.py`: 사이트에 접속해서 원본 HTML, rendered HTML, asset, sheet JSON, PDF를 raw로 저장한다.
- `processor.py`: 저장된 `raw/*/manifest.jsonl`을 읽어 documents/chunks/errors를 생성한다.
- `pipeline.py`: `raw`, `process`, `run`, `build-vector` 명령 흐름을 조합한다.

이 구조를 선택한 이유는 이미 수집한 raw data를 재사용해서 전처리와 vector store만 다시 만들 수 있게 하기 위해서다. 대용량 PDF나 SPA 렌더링 때문에 raw 수집이 오래 걸려도, chunking/embedding 전략을 바꿀 때 다시 크롤링할 필요가 없다.

| 사이트 | 구조 | adapter | 주요 수집 방식 |
| --- | --- | --- | --- |
| `aic.kaist.ac.kr` | Vite/React SPA | `ViteReactSpaAdapter` | HTML shell, JS bundle, route fallback, PDF |
| `ai-systems.kaist.ac.kr` | 정적 HTML | `StaticHtmlAdapter` | same-origin HTML link, PDF |
| `ax.kaist.ac.kr` | Vite/React SPA | `ViteReactSpaAdapter` | Playwright 렌더링 route, JS bundle, PDF |
| `fx.kaist.ac.kr` | SPA + Google Sheets | `FxSheetsSpaAdapter` | Playwright 렌더링 route, gviz JSON, dynamic route |
| `www.kaist.ac.kr/kr/` | 정적 HTML | `StaticHtmlAdapter` | `/kr/` 및 주요 `/kr/html/` 범위 제한 수집 |
| `aicollege.kaist.ac.kr` | Vite/React SPA | `ViteReactSpaAdapter` | HTML shell, JS/CSS asset, route fallback |

## SPA 렌더링 전략

SPA 사이트는 단순 HTTP 요청만으로는 실제 사용자 화면의 DOM 텍스트가 부족할 수 있다. 그래서 `ViteReactSpaAdapter`는 다음 순서로 수집한다.

1. root HTML shell을 raw로 저장한다.
2. JS/CSS asset을 찾아 raw로 저장한다.
3. JS bundle에서 의미 있는 한글/영문 문자열과 파일 링크를 추출한다.
4. 설정된 route를 Playwright로 렌더링해 rendered HTML을 저장한다.
5. 렌더링이 실패하면 해당 route는 일반 HTML shell 저장으로 fallback한다.
6. 첫 route부터 렌더링이 실패하면 해당 도메인의 브라우저 렌더링이 불안정하다고 보고 나머지 route는 즉시 shell fallback으로 저장한다.

렌더링 기본값은 `domcontentloaded` 후 1초 대기다. `networkidle`은 analytics, font, 장시간 연결 때문에 수집이 과도하게 길어질 수 있어서 기본값으로 쓰지 않는다.

raw 단계에서는 rendered HTML 저장까지만 수행하고 DOM 텍스트 추출은 하지 않는다. 텍스트 추출은 processor가 raw HTML을 읽으면서 수행한다.

현재 환경에서 확인한 결과:

- `ax.kaist.ac.kr`은 Playwright 렌더링이 정상 동작했다.
- `aic.kaist.ac.kr`, `aicollege.kaist.ac.kr`은 Chromium에서 route load가 timeout되므로 fallback이 필요하다.
- fallback이 발생해도 root HTML, JS bundle, PDF raw 저장은 계속 수행된다.

## PDF 수집 및 텍스트 추출

PDF URL은 먼저 실제 다운로드 응답인지 검증한다.

- URL 확장자가 `.pdf`여도 서버가 SPA fallback HTML을 반환하면 PDF로 저장하지 않는다.
- content-type 또는 `%PDF` header를 확인해 실제 PDF만 `raw/<site>/files/`에 저장한다.
- 원본 PDF는 항상 raw data로 보존한다.
- `raw` 명령은 PDF 원본 저장까지만 수행하고 텍스트 추출은 하지 않는다.
- `run` 명령은 raw 저장 이후 processed 문서를 만들 때 PDF 텍스트를 추출한다.

텍스트 추출은 다음 순서로 시도한다.

1. `pymupdf`
2. `pdfplumber`
3. `pypdf`
4. `PyPDF2`

추출에 성공하면 `Document` metadata에 `document_type=pdf`, `pdf_extractor`, `pdf_pages`를 기록한다. 추출 실패 시 원본 PDF는 보존하고 실패 사유만 errors에 남긴다.

## 사이트별 방식

### AIC

- Vite/React SPA다.
- sitemap endpoint는 XML이 아니라 SPA index HTML을 반환하므로 sitemap 기반 수집은 사용하지 않는다.
- 현재 환경에서는 Playwright 렌더링이 timeout되므로 shell 및 JS bundle 기반 fallback을 유지한다.
- known PDF:
  - `/files/AI_Computing_Grad_Info_Session_20260320.pdf`
  - `/files/AI_Computing_Introduction_20260526.pdf`

### AI Systems

- 정적 HTML 사이트다.
- `/`, `/news.html`, `/admission-ug.html`, `/admission-grad.html` 중심으로 수집한다.
- 같은 origin의 HTML link를 따라가고 attachment PDF를 다운로드한다.
- Playwright가 필요 없다.

### AX

- Vite/React SPA다.
- wrong-domain sitemap directive가 있어 sitemap을 신뢰하지 않는다.
- 현재 환경에서 Playwright 렌더링이 정상 동작한다.
- route별 rendered HTML이 raw에 저장되고, rendered DOM 텍스트가 processed 문서에 들어간다.
- known PDF:
  - `/files/20260318_AX학과_2026년_가을입학_입시설명회_VER3.pdf`

### FX

- Vite/React SPA이며 news/faculty 데이터는 public Google Sheets gviz JSON에서 온다.
- root와 주요 route는 Playwright 렌더링을 시도한다.
- `news`, `faculty` sheet는 raw JSON으로 저장하고 row를 문서로 변환한다.
- sheet 기반 slug로 news/faculty dynamic route를 만들어 추가 수집한다.

### KAIST 본원

- 정적 HTML 중심의 공식 사이트다.
- 전체 사이트를 모두 따라가면 범위가 너무 넓어지므로 `/kr/` 및 주요 `/kr/html/` 섹션으로 제한한다.
- footer, news, site map, English section, 반복 404 path는 제외한다.
- 현재 최대 수집 페이지 수는 80개다.

### AI College

- Vite/React SPA다.
- sitemap은 SPA HTML fallback이므로 사용하지 않는다.
- 현재 환경에서는 Playwright 렌더링이 timeout될 수 있어 shell 및 JS/CSS asset 저장을 fallback으로 사용한다.

## Raw Data 저장 원칙

raw data는 가능한 원본에 가깝게 보존한다.

- HTML shell과 rendered HTML은 `raw/<site>/pages/`에 저장한다.
- JavaScript/CSS asset은 `raw/<site>/assets/`에 저장한다.
- PDF 같은 다운로드 파일은 `raw/<site>/files/`에 저장한다.
- FX Google Sheets gviz JSON은 `raw/kaist_fx/sheets/`에 저장한다.
- 모든 raw 파일은 `manifest.jsonl`에 source URL, canonical URL, content-type, sha256, 저장 경로, metadata를 기록한다.
- raw 단계에서 file policy로 제외한 파일은 `raw/<site>/skipped_files.jsonl`에 URL과 제외 사유를 기록한다.

## Raw File Policy

다른 대학원 사이트로 확장할 때도 raw 수집은 가능한 원본 보존을 우선하지만, 파일 다운로드는 예외적으로 사전 제한한다. 이유는 대용량 뉴스레터, 매거진, 연례보고서처럼 RAG 품질 대비 비용이 큰 파일이 raw 수집 시간을 크게 늘릴 수 있기 때문이다.

현재 기본 정책은 `configs/kaist_ai_sources.yml`의 `defaults.raw.file_policy`에 둔다.

- `max_file_size_mb`: 기본 30MB를 초과하는 파일은 다운로드하지 않는다.
- `exclude_url_patterns`: newsletter, kaistian, magazine, annual, report, 소식지 패턴은 제외한다.
- `include_url_patterns`: 특정 사이트에서 반드시 포함해야 하는 파일이 있으면 source별로 override한다.
- `skip_unknown_size`: 서버가 `content-length`를 주지 않아도 기본적으로는 다운로드를 시도한다.

이 정책은 모든 사이트에 공통 적용하고, 사이트별 예외만 설정에서 override한다. 그래서 새 대학원 사이트를 추가할 때 코드 수정 없이 YAML만으로 대용량/저관련 파일 정책을 조정할 수 있다.

## 전처리 범위

raw 수집 단계에서는 PDF 텍스트 추출, 강한 노이즈 제거, 정형화, 중복 제거를 하지 않는다. 이유는 다음과 같다.

- raw data는 재현성과 감사 가능성이 중요하다.
- 중복 제거를 수집 중에 강하게 하면 나중에 원인을 추적하기 어렵다.
- route shell, rendered HTML, PDF 추출문처럼 출처가 다른 텍스트는 processed 단계에서 품질 기준을 정해 병합하는 편이 안전하다.

따라서 raw 수집 단계는 원본 보존과 출처 metadata 기록에 집중하고, PDF 텍스트 추출, 중복 제거, 품질 정리는 processed/chunk 단계에서 처리한다. 전처리에서 제외된 항목은 `processed/filtered.jsonl`에 남겨 어떤 기준 때문에 벡터 대상에서 빠졌는지 추적한다.

현재 기본 전처리 필터는 다음을 제외한다.

- 같은 sha256을 가진 중복 raw 파일
- 같은 정규화 텍스트를 가진 중복 문서
- 같은 정규화 텍스트를 가진 중복 chunk
- 텍스트가 너무 짧은 문서
- SPA route HTML shell
- 30MB 초과 PDF
- newsletter, kaistian, magazine, annual, report, 소식지 패턴의 PDF
- vendor 성격의 JavaScript asset

KAIST 본원 사이트는 사이트 범위가 넓기 때문에 processed 단계에서 HTML 문서를 `/kr/html/admission/`, `/kr/html/edu/` 중심으로 제한한다. 본원 사이트의 일반 소개, 캠퍼스, 연구 홍보, 뉴스레터는 AI 대학원 RAG의 핵심 질문에 비해 노이즈가 될 가능성이 높기 때문이다.

## 실행 명령

raw 수집만 수행한다.

```powershell
python -m kaist_crawler raw --config configs\kaist_ai_sources.yml --output data
```

기존 raw data를 전처리한다.

```powershell
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data
```

raw 수집, 전처리, vector 생성을 한 번에 수행한다.

```powershell
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data
```

재수집 전 출력물을 정리하려면 `--clean`을 사용한다.

```powershell
python -m kaist_crawler raw --config configs\kaist_ai_sources.yml --output data --clean
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --clean
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data --clean
```

## 검증 명령

문법 검사는 다음 명령으로 수행한다.

```powershell
python -m py_compile kaist_crawler\__main__.py kaist_crawler\__init__.py kaist_crawler\models.py kaist_crawler\config.py kaist_crawler\http_client.py kaist_crawler\store.py kaist_crawler\extractors.py kaist_crawler\rendering.py kaist_crawler\policies.py kaist_crawler\processor.py kaist_crawler\vector_store.py kaist_crawler\adapters.py kaist_crawler\pipeline.py kaist_crawler\cli.py
```

AX 기준 SPA 렌더링과 PDF 추출이 processed까지 들어가는지 확인하려면 다음 명령을 사용한다.

```powershell
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data_test --source kaist_ax --skip-vector
```

예상되는 핵심 결과:

- `processed/documents.jsonl`에 `document_type=rendered_html` 문서가 생성된다.
- `processed/documents.jsonl`에 `document_type=pdf` 문서가 생성된다.
- PDF metadata에 `pdf_extractor`, `pdf_pages`가 기록된다.

## 확장 방법

새 대학원 사이트를 추가할 때는 먼저 구조를 판별한다.

- 정적 HTML이면 `static_html`
- Vite/React SPA이면 `vite_react_spa`
- SPA 외부 데이터 소스가 있으면 별도 adapter 또는 기존 adapter 확장

확장 시 지켜야 할 원칙:

- raw data를 먼저 저장한다.
- 다운로드 파일은 실제 파일 응답인지 검증한다.
- 대용량/저관련 파일은 raw file policy로 제한하고 제외 기록을 남긴다.
- 텍스트 추출은 raw data에서 재현 가능해야 한다.
- RAG 품질 기준은 processing filter policy에서 조정하고 제외 기록을 남긴다.
- 실패는 errors에 기록하고 다음 URL 수집을 계속한다.
- metadata에는 citation에 필요한 source URL과 raw path를 남긴다.
