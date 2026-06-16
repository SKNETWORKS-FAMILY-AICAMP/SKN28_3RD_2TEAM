# KAIST AI 대학원 크롤링 전략

마지막 확인일: 2026-06-16

## 목표

대학원 사이트 URL을 입력하면 다음 작업이 한 번에 이어지는 Python 파이프라인을 만든다.

1. 공개 페이지와 첨부 파일을 raw data로 저장한다.
2. PDF 같은 다운로드 자료를 자동으로 내려받는다.
3. HTML, JavaScript bundle, Google Sheets JSON, PDF에서 텍스트를 추출한다.
4. RAG 챗봇에 넣기 좋은 크기로 chunk를 만든다.
5. chunk를 기반으로 vector store를 생성한다.

첫 대상은 KAIST AI 관련 학과 사이트 4개였고, 현재는 KAIST 본원 한국어 사이트와 KAIST College of AI 사이트까지 포함한다.

1. `https://aic.kaist.ac.kr/`
2. `https://ai-systems.kaist.ac.kr/`
3. `https://ax.kaist.ac.kr/`
4. `https://fx.kaist.ac.kr/`
5. `https://www.kaist.ac.kr/kr/`
6. `https://aicollege.kaist.ac.kr/`

네 사이트는 구조가 서로 다르기 때문에 하나의 generic crawler만 쓰면 데이터가 누락될 가능성이 높다. 그래서 이 프로젝트는 site adapter 방식을 사용한다.

## 요약

| 사이트 | 관찰된 구조 | 주요 발견 방식 | 사용 adapter |
| --- | --- | --- | --- |
| `aic.kaist.ac.kr` | Vite/React SPA | JS bundle route, known file | `ViteReactSpaAdapter` |
| `ai-systems.kaist.ac.kr` | 정적 HTML | same-origin HTML link | `StaticHtmlAdapter` |
| `ax.kaist.ac.kr` | Vite/React SPA | JS bundle route, known file | `ViteReactSpaAdapter` |
| `fx.kaist.ac.kr` | Vite/React SPA + Google Sheets | gviz JSON, dynamic route | `FxSheetsSpaAdapter` |
| `www.kaist.ac.kr/kr/` | 정적 HTML + 정상 sitemap | bounded same-origin HTML link | `StaticHtmlAdapter` |
| `aicollege.kaist.ac.kr` | Vite/React SPA | JS/CSS assets + configured routes | `ViteReactSpaAdapter` |

핵심 판단은 다음과 같다.

- 네 사이트 모두 sitemap XML에 의존하면 안 된다.
- `aic`, `ax`, `fx`는 `/`를 단순 HTTP 요청하면 대부분 app shell만 온다.
- `ai-systems`는 주요 본문이 HTML에 직접 들어 있어 정적 파싱으로 충분하다.
- `fx`는 뉴스와 교수진 데이터가 public Google Sheets gviz JSON에서 온다.
- KAIST 본원은 링크가 넓게 퍼지므로 `/kr/` 하위 핵심 섹션만 제한 수집한다.
- AI College는 sitemap이 SPA HTML fallback이라 bundle과 route 설정을 기준으로 수집한다.

## 현재 구현 상태

현재 폴더에는 동작하는 fallback 파이프라인이 들어 있다.

- `configs/kaist_ai_sources.yml`에 6개 사이트 설정을 분리했다.
- `kaist_crawler` 패키지에 수집, 저장, 추출, chunking, vector 생성을 구현했다.
- `StaticHtmlAdapter`는 AI Systems를 정적 HTML로 수집한다.
- `ViteReactSpaAdapter`는 AIC와 AX의 app shell, JS asset, route shell, known PDF를 저장한다.
- `FxSheetsSpaAdapter`는 FX의 Google Sheets `news`, `faculty` 데이터를 추가로 수집한다.
- `processed/errors.jsonl`에 비치명적 오류를 기록한다. raw-only 실행에서는 `processed/`를 만들지 않는다.

2026-06-16 기준 전체 6개 사이트 raw-only 검증 결과:

- raw 파일: 184개
- 실제 PDF 다운로드: 17개
- source manifest: 6개
- 수집 중 비치명적 오류: 0개
- `processed/`, `vector/`: 생성하지 않음

현재 한계:

- SPA adapter는 아직 Playwright 렌더링을 실행하지 않는다.
- 따라서 AIC/AX의 route별 user-visible DOM 텍스트를 완전히 얻으려면 Playwright 추가가 필요하다.
- 현재 방식은 raw 보존, JS bundle 텍스트 추출, known route shell 저장, known file 다운로드, FX sheet-backed record 수집에 초점을 둔다.

## 사이트별 분석

### KAIST AI Computing

Base URL: `https://aic.kaist.ac.kr/`

관찰된 구조:

- Vite/React single-page app이다.
- root HTML에서 `assets/index-DH01CeZq.js`를 참조했다.
- `robots.txt`는 `/`를 허용하고 `https://aic.kaist.ac.kr/sitemap.xml`을 sitemap으로 선언했다.
- 하지만 `sitemap.xml`, `sitemap_index.xml`은 XML이 아니라 SPA index HTML을 반환했다.
- JS bundle에서 route 문자열이 확인됐다.
  - `/`
  - `/welcome-message`
  - `/dept-intro`
  - `/people`
  - `/admission-ug`
  - `/admission-grad`
  - `/education-courses`
  - `/education-reqs`
  - `/notice`
- 확인된 다운로드 파일:
  - `/files/AI_Computing_Grad_Info_Session_20260320.pdf`
  - `/files/AI_Computing_Introduction_20260526.pdf`

선택한 수집 방식:

1. root HTML을 raw로 저장한다.
2. root HTML에서 JS asset 경로를 찾고 bundle을 저장한다.
3. JS bundle에서 의미 있는 문자열과 파일 링크를 추출한다.
4. 설정된 route shell을 저장한다.
5. `/files/...`의 known PDF를 다운로드한다.
6. 나중에 Playwright를 추가하면 route별 렌더링 DOM 텍스트를 보강한다.

이 방식을 선택한 이유:

- 사이트가 client-rendered라 단순 HTML 요청만으로는 실제 본문이 부족하다.
- sitemap endpoint가 정상 XML이 아니라서 sitemap 기반 수집이 불안정하다.
- route 수가 작고 명확해 제한된 route 수집이 안전하다.

장점:

- raw HTML, JS bundle, PDF를 재현 가능한 형태로 보존한다.
- 잘못된 sitemap 때문에 다른 도메인이나 fallback HTML을 수집하는 문제를 줄인다.
- Playwright 추가 전에도 기본 자료와 파일을 확보할 수 있다.

단점:

- 현재 상태에서는 route별 렌더링 결과의 텍스트 품질이 제한된다.
- JS bundle hash가 바뀌면 매번 현재 asset 경로를 다시 찾아야 한다.

### KAIST AI Systems

Base URL: `https://ai-systems.kaist.ac.kr/`

관찰된 구조:

- 정적 HTML 페이지다.
- root page에서 아래 페이지로 이동한다.
  - `/news.html`
  - `/admission-ug.html`
  - `/admission-grad.html`
- `robots.txt`, `sitemap.xml`, `sitemap_index.xml`은 확인 당시 404였다.
- 입학 안내 본문이 HTML에 직접 들어 있다.
- 확인된 다운로드 파일:
  - `/attachments/AI_Systems_Grad_Info_20260319.pdf`

선택한 수집 방식:

1. `/`에서 시작한다.
2. same-origin `.html` 링크를 찾는다.
3. HTML을 직접 요청한다.
4. BeautifulSoup으로 본문 텍스트를 추출한다.
5. `/attachments/...` 파일을 다운로드한다.

이 방식을 선택한 이유:

- 브라우저 렌더링 없이도 주요 텍스트가 HTML에 들어 있다.
- 페이지 수가 작고 navigation link가 명확하다.
- sitemap이 없으므로 사이트 내부 link 기반 발견이 더 현실적이다.

장점:

- 가장 빠르고 단순하다.
- 테스트가 쉽다.
- Playwright 의존성이 필요 없다.

단점:

- navigation에 연결되지 않은 새 HTML 페이지는 놓칠 수 있다.
- 변경 감지를 위한 sitemap이 없다.

### KAIST AX

Base URL: `https://ax.kaist.ac.kr/`

관찰된 구조:

- Vite/React single-page app이다.
- root HTML에서 `assets/index-DWuM8sBL.js`를 참조했다.
- `robots.txt`는 crawl을 허용하지만 sitemap이 `https://aic.kaist.ac.kr/sitemap.xml`로 되어 있었다.
- 즉 AX 도메인이 아니라 AIC 도메인을 가리키는 잘못된 sitemap directive다.
- `sitemap.xml`, `sitemap_index.xml`은 XML이 아니라 SPA index HTML을 반환했다.
- JS bundle에서 route 문자열이 확인됐다.
  - `/`
  - `/welcome-message`
  - `/dept-intro`
  - `/people`
  - `/admission-ug`
  - `/admission-grad`
  - `/education-courses`
  - `/education-reqs`
  - `/notice`
- 확인된 다운로드 파일:
  - `/files/20260318_AX학과_2026년_가을입학_입시설명회_VER3.pdf`

선택한 수집 방식:

1. root HTML과 JS bundle을 raw로 저장한다.
2. cross-domain sitemap directive는 사용하지 않는다.
3. 설정된 route shell을 저장한다.
4. JS bundle과 설정 파일에서 확인한 `/files/...` PDF를 다운로드한다.
5. Playwright 추가 시 route별 렌더링 본문을 보강한다.

이 방식을 선택한 이유:

- AIC와 마찬가지로 client-rendered 구조다.
- 잘못된 sitemap을 따르면 AX가 아니라 AIC 데이터를 수집할 수 있다.
- route와 PDF가 명확하므로 제한된 수집이 안전하다.

장점:

- wrong-domain sitemap으로 인한 데이터 오염을 피한다.
- admissions briefing PDF를 명시적으로 확보한다.
- SPA raw data를 재수집 없이 다시 분석할 수 있다.

단점:

- 현재 route별 텍스트 추출 품질은 Playwright 도입 전까지 제한된다.
- 사이트가 build될 때 asset 이름이 바뀔 수 있다.

### KAIST AI and Futures Studies

Base URL: `https://fx.kaist.ac.kr/`

관찰된 구조:

- Vite/React single-page app이다.
- root HTML에서 `assets/index-xaSox8S-.js`를 참조했다.
- `robots.txt`, `sitemap.xml`, `sitemap_index.xml`은 robots/sitemap 문서가 아니라 SPA index HTML을 반환했다.
- JS bundle에서 route가 확인됐다.
  - `/`
  - `/about`
  - `/faculty`
  - `/faculty-card/:slug`
  - `/curriculum`
  - `/news`
  - `/news/:slug`
- dynamic JS chunk가 있다.
  - `assets/Faculty-BJ8b-wBN.js`
  - `assets/faculty-_SHVcc7d.js`
  - `assets/FacultyCard-BKBLSE9s.js`
- 뉴스와 교수진 데이터는 public Google Sheets gviz endpoint에서 로드된다.
- spreadsheet ID:
  - `1Y3HuFoK0Zu9WAsiTsqaCxbyXZTJxMP_XkQ_uCHSPN5A`
- sheet:
  - `news`
  - `faculty`
- gviz URL pattern:
  - `https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:json&headers=1&sheet={sheet}`

선택한 수집 방식:

1. root HTML, main JS, dynamic JS chunk를 저장한다.
2. `news`, `faculty` sheet의 gviz JSON을 raw로 저장한다.
3. gviz row를 내부 record로 정규화한다.
4. `news.slug`로 `/news/{slug}` URL을 만든다.
5. `faculty.name_en`으로 `/faculty-card/{slug}` URL을 만든다.
6. sheet row를 문서로 변환해 vector 대상에 포함한다.

이 방식을 선택한 이유:

- FX의 핵심 정보는 렌더링 결과뿐 아니라 Google Sheets 원천 데이터에 들어 있다.
- `/news` 화면만 수집하면 개별 뉴스 본문을 놓칠 수 있다.
- gviz JSON을 raw로 저장하면 나중에 live sheet가 바뀌어도 당시 수집 결과를 재현할 수 있다.

장점:

- FX에서 가장 중요한 구조화 데이터인 news/faculty row를 직접 확보한다.
- 교수진, 뉴스, slug, category 같은 metadata를 깨끗하게 유지할 수 있다.
- dynamic route를 자동으로 만들 수 있다.

단점:

- Google Sheets 접근 가능 여부에 영향을 받는다.
- sheet image까지 다운로드하려면 별도의 이미지 URL resolver가 필요하다.

### KAIST 본원 한국어 사이트

Base URL: `https://www.kaist.ac.kr/kr/`

관찰된 구조:

- 정적 HTML 중심의 KAIST 공식 한국어 사이트다.
- `robots.txt`는 전체 경로 수집을 허용한다.
- `sitemap.xml`은 정상 XML이지만 top-level URL 위주로 제한적이다.
- root page의 menu/footer에는 내부 링크와 외부 부속기관 링크가 매우 많다.
- 일부 menu placeholder URL은 실제로 404를 반환한다.

선택한 수집 방식:

1. `/kr/`에서 시작한다.
2. sitemap top-level 성격의 핵심 route를 명시적으로 넣는다.
3. same-domain HTML 링크를 따라가되 `/kr/`와 `/kr/html/{kaist,admission,edu,research,campus}/` 하위로 제한한다.
4. footer, news, site map, English section은 제외한다.
5. 최대 수집 페이지 수를 80개로 제한한다.
6. 확인된 broken path는 `exclude_paths`에 넣어 반복 404를 피한다.

이 방식을 선택한 이유:

- 본원 사이트 전체를 열어두면 부속기관, 외부 사이트, footer/legal 페이지까지 과도하게 퍼진다.
- RAG에 필요한 기본 KAIST 소개, 입학, 교육, 연구, 캠퍼스 정보는 `/kr/html/` 핵심 섹션에 모여 있다.
- sitemap은 정상이나 너무 상위 URL 중심이라 menu link 기반 보강이 필요하다.

장점:

- KAIST 공식 기본 정보를 raw로 확보할 수 있다.
- 무제한 크롤링으로 인한 데이터 오염을 줄인다.
- broken link를 설정으로 관리할 수 있다.

단점:

- 제한 수집이므로 본원 뉴스 전체나 footer의 모든 행정 문서는 포함하지 않는다.
- 본원 사이트 구조가 바뀌면 include/exclude path를 다시 점검해야 한다.

### KAIST College of AI

Base URL: `https://aicollege.kaist.ac.kr/`

관찰된 구조:

- Vite/React single-page app이다.
- root HTML은 `/assets/index-FwXjtZow.js`, `/assets/vendor-BD9HwwPS.js`, `/assets/index-B_3tsJJu.css`를 참조한다.
- `robots.txt`는 수집을 허용하고 sitemap을 선언한다.
- 하지만 `sitemap.xml`은 XML이 아니라 SPA index HTML을 반환한다.
- JS bundle에서 주요 route가 확인됐다.
  - `/`
  - `/intro`
  - `/departments`
  - `/admissions`
  - `/course-information`
  - `/graduation-requirements`
  - `/notice`
  - `/notice/ai-college-vision-declaration`
  - `/notice/global-ai-hub-statement`

선택한 수집 방식:

1. root HTML을 raw로 저장한다.
2. JS/CSS asset을 raw로 저장한다.
3. JS bundle에서 의미 있는 텍스트를 추출할 수 있게 보존한다.
4. 확인된 route shell을 저장한다.
5. sitemap은 사용하지 않는다.

이 방식을 선택한 이유:

- sitemap endpoint가 SPA HTML fallback이라 discovery source로 신뢰하기 어렵다.
- 중요한 route 수가 명확하고 적다.
- 브라우저 렌더링 전에도 app shell과 bundle을 보존하면 이후 재처리가 가능하다.

장점:

- KAIST College of AI 상위 조직 정보를 4개 학과 데이터와 함께 보존할 수 있다.
- JS/CSS asset까지 저장하므로 SPA 구조 분석이 가능하다.

단점:

- 현재는 Playwright 렌더링 전이므로 route별 실제 화면 텍스트 품질은 제한된다.

## 권장 아키텍처

```text
입력 URL 또는 source id
  -> config lookup
  -> adapter 선택
  -> discovery
  -> raw fetch 및 file download
  -> text extraction
  -> chunking
  -> vector store build
```

adapter를 분리한 이유:

- AIC와 AX는 SPA라서 일반 HTML crawler만으로는 부족하다.
- AI Systems는 정적 HTML이라 단순 fetch가 더 효율적이다.
- FX는 SPA와 Google Sheets 수집이 함께 필요하다.
- 네 사이트 모두 sitemap 품질이 좋지 않다.

## Raw Data 저장 원칙

raw data는 가능한 한 원본에 가깝게 보존한다.

- HTML은 `raw/<site>/pages/`에 저장한다.
- JavaScript bundle은 `raw/<site>/assets/`에 저장한다.
- PDF 같은 다운로드 파일은 `raw/<site>/files/`에 저장한다.
- FX gviz JSON은 `raw/kaist_fx/sheets/`에 저장한다.
- KAIST 본원 한국어 사이트는 `raw/kaist_main_kr/`에 저장한다.
- KAIST College of AI 사이트는 `raw/kaist_ai_college/`에 저장한다.
- 모든 raw 파일은 `manifest.jsonl`에 metadata를 남긴다.

manifest record 예시:

```json
{
  "source_id": "stable unique id",
  "site": "kaist_aic",
  "adapter": "vite_react_spa",
  "source_url": "https://aic.kaist.ac.kr/admission-grad",
  "canonical_url": "https://aic.kaist.ac.kr/admission-grad",
  "content_type": "text/html",
  "raw_path": "data/raw/kaist_aic/pages/admission-grad.html",
  "sha256": "...",
  "fetched_at": "2026-06-16T00:00:00+09:00",
  "metadata": {
    "route": "/admission-grad",
    "rendered": false
  }
}
```

## Text Extraction

현재 구현된 추출 방식:

- HTML: BeautifulSoup으로 `script`, `style`, `noscript`, `svg`를 제거한 뒤 본문 텍스트를 추출한다.
- JS bundle: template literal과 JSON string literal에서 의미 있는 한글/영문 텍스트를 추출한다.
- PDF: `pypdf` 또는 `PyPDF2`가 설치되어 있으면 본문 텍스트를 추출한다.
- FX gviz row: row field를 `key: value` 형태의 문서로 변환한다.

추가하면 좋은 추출 방식:

- Playwright DOM text extraction
- PyMuPDF 기반 PDF extraction
- DOCX extraction
- HWP/HWPX 전용 converter
- admission schedule table 보존 chunking

## Vector Store

현재는 두 가지 vector 출력 형식을 만든다.

```text
data/vector/simple/chunks.jsonl
data/vector/chroma/
```

`simple/chunks.jsonl`은 chunk metadata와 embedding vector를 JSONL로 저장한다. Chroma가 설치되어 있으면 같은 chunk를 `data/vector/chroma/`에도 upsert한다.

embedding provider는 두 가지다.

- `hash`: 외부 API 없이 파이프라인을 검증하기 위한 fallback이다.
- `openai`: 운영용 RAG에 사용할 provider다.

OpenAI embedding 사용 방식:

```powershell
$env:OPENAI_API_KEY = "sk-..."
python -m kaist_crawler build-vector --input data\processed\chunks.jsonl --output data --embedding-provider openai
```

기본 OpenAI embedding 모델은 `text-embedding-3-large`다. 비용을 줄이고 싶으면 `--embedding-model text-embedding-3-small`을 지정한다.

OpenAI 공식 문서 기준으로 `text-embedding-3-small`의 기본 vector 길이는 1536, `text-embedding-3-large`의 기본 vector 길이는 3072다. `dimensions` parameter를 사용하면 더 짧은 vector로 줄일 수 있으므로, 필요하면 `--embedding-dimensions`를 사용한다.

Chroma collection 이름은 provider/model/dimensions에서 자동 생성한다. 예를 들어 OpenAI large 기본 설정은 `kaist_ai_openai_text-embedding-3-large_3072` 형식으로 저장되어 hash embedding collection과 충돌하지 않는다.

각 chunk metadata에는 최소한 아래 값이 포함된다.

- `site`
- `source_url`
- `title`
- `document_type`
- `raw_path`
- `chunk_index`
- `embedding_provider`
- `embedding_model`
- `embedding_dimensions`

## 한글 깨짐 확인

현재 Markdown 파일은 UTF-8로 저장한다. 터미널에서 깨져 보이는 경우는 파일 내용이 깨진 것이 아니라 PowerShell 출력 인코딩 문제일 수 있다.

파일 자체 검증 방법:

```powershell
python -c "from pathlib import Path; p=Path('docs/kaist-crawling-strategy.md'); text=p.read_text(encoding='utf-8'); markers=[chr(0xfffd), chr(0x5a9b), '?' + chr(0xc206)]; print('utf8 ok', len(text)); print(any(x in text for x in markers))"
```

위 명령에서 `utf8 ok`가 출력되고 마지막 값이 `False`면 파일 자체는 깨지지 않은 것이다.

PowerShell 표시를 UTF-8로 바꾸려면 다음을 실행한다.

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
```

## 확장 방법

새 대학원 사이트를 추가할 때는 먼저 `configs/kaist_ai_sources.yml`에 source를 추가한다.

정적 HTML이면 `static_html` adapter를 사용한다.

Vite/React SPA이면서 데이터가 JS bundle 안에 있으면 `vite_react_spa`를 사용한다.

별도 API나 Google Sheets처럼 외부 data source가 있으면 새 adapter를 추가하는 것이 안전하다.

새 adapter를 추가할 때 지켜야 할 원칙:

- raw data를 먼저 저장한다.
- text extraction은 raw data에서 재현 가능해야 한다.
- 다운로드 파일은 content-type을 검증한다.
- 실패는 가능한 한 `errors.jsonl`에 남기고 다음 URL 수집을 계속한다.
- chunk metadata에 citation에 필요한 URL과 raw path를 남긴다.
