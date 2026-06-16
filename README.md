# KAIST AI 대학원 크롤러

KAIST AI 관련 학과 사이트와 KAIST 본원/AI College 사이트를 수집해서 RAG 챗봇에 넣을 수 있는 raw data, 처리 문서, chunk, vector store를 만드는 Python 크롤러입니다.

현재 대상 사이트는 다음과 같습니다.

- `https://aic.kaist.ac.kr/`
- `https://ai-systems.kaist.ac.kr/`
- `https://ax.kaist.ac.kr/`
- `https://fx.kaist.ac.kr/`
- `https://www.kaist.ac.kr/kr/`
- `https://aicollege.kaist.ac.kr/`

이 프로젝트는 `C:\Users\Playdata\workspace\kaist_ai_crawler_project` 폴더 안에서 독립적으로 동작합니다. 기존 프로젝트 파일은 건드리지 않습니다.

## 실행 방법

전체 6개 사이트를 수집하고 vector store까지 생성합니다.

```powershell
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data
```

raw data만 만들 때는 아래 명령을 사용합니다. 이 명령은 `processed/`와 `vector/`를 만들지 않습니다.

```powershell
python -m kaist_crawler raw --config configs\kaist_ai_sources.yml --output data
```

특정 사이트 하나만 수집할 수도 있습니다.

```powershell
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data --source kaist_ai_systems
```

이미 만들어진 chunk 파일로 vector store만 다시 만들 때는 아래 명령을 사용합니다.

```powershell
python -m kaist_crawler build-vector --input data\processed\chunks.jsonl --output data
```

OpenAI embedding으로 vector store를 만들 때는 `OPENAI_API_KEY`를 환경변수로 설정하고 `--embedding-provider openai`를 사용합니다.

```powershell
$env:OPENAI_API_KEY = "sk-..."
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data_openai --embedding-provider openai
```

이미 `chunks.jsonl`이 있다면 vector만 다시 만들 수 있습니다.

```powershell
$env:OPENAI_API_KEY = "sk-..."
python -m kaist_crawler build-vector --input data\processed\chunks.jsonl --output data --embedding-provider openai
```

기본 OpenAI embedding 모델은 `text-embedding-3-large`입니다. 비용을 줄이고 싶으면 `--embedding-model text-embedding-3-small`을 지정합니다.

## 폴더 구조

```text
kaist_ai_crawler_project/
  configs/
    kaist_ai_sources.yml
  docs/
    kaist-crawling-strategy.md
  kaist_crawler/
    __main__.py
    cli.py
    pipeline.py
    adapters.py
    config.py
    http_client.py
    store.py
    extractors.py
    vector_store.py
    models.py
  README.md
```

## 출력 구조

크롤링 결과는 `--output`으로 지정한 폴더 아래에 저장됩니다.

```text
data/
  raw/
    kaist_aic/
      manifest.jsonl
      pages/
      assets/
      files/
    kaist_ai_systems/
      manifest.jsonl
      pages/
      files/
    kaist_ax/
      manifest.jsonl
      pages/
      assets/
      files/
    kaist_fx/
      manifest.jsonl
      pages/
      assets/
      sheets/
      files/
    kaist_main_kr/
      manifest.jsonl
      pages/
      files/
    kaist_ai_college/
      manifest.jsonl
      pages/
      assets/
  processed/
    documents.jsonl
    chunks.jsonl
    errors.jsonl
  vector/
    simple/
      chunks.jsonl
    chroma/
```

각 출력의 의미는 다음과 같습니다.

- `raw/`: 원본 HTML, JavaScript, Google Sheets JSON, PDF 같은 다운로드 파일을 그대로 저장합니다.
- `manifest.jsonl`: raw 파일마다 원본 URL, 저장 경로, content-type, sha256, 수집 시각을 기록합니다.
- `processed/documents.jsonl`: raw data에서 추출한 문서 단위 텍스트입니다.
- `processed/chunks.jsonl`: vector store에 넣기 위해 문서를 작은 단위로 나눈 결과입니다.
- `processed/errors.jsonl`: 수집 중 발생한 비치명적 오류입니다. 오류가 없어도 빈 파일로 생성됩니다.
- `vector/simple/chunks.jsonl`: chunk와 deterministic hash embedding을 같이 저장한 간단한 vector 파일입니다.
- `vector/chroma/`: Chroma가 설치되어 있으면 생성되는 로컬 Chroma vector store입니다.

## 사이트별 수집 방식

현재 크롤러는 사이트 구조에 따라 adapter를 다르게 사용합니다.

- `StaticHtmlAdapter`
  - 대상: `ai-systems.kaist.ac.kr`, `www.kaist.ac.kr/kr/`
  - 정적 HTML 페이지를 직접 요청하고 BeautifulSoup으로 텍스트를 추출합니다.
  - KAIST 본원은 `/kr/` 하위 공식 HTML만 최대 80개까지 제한 수집합니다.

- `ViteReactSpaAdapter`
  - 대상: `aic.kaist.ac.kr`, `ax.kaist.ac.kr`, `aicollege.kaist.ac.kr`
  - Vite/React SPA 사이트의 HTML shell, JS bundle, 설정된 route shell, PDF 파일을 저장합니다.
  - 현재는 브라우저 렌더링 없이 raw 보존과 JS bundle 텍스트 추출을 수행합니다.

- `FxSheetsSpaAdapter`
  - 대상: `fx.kaist.ac.kr`
  - SPA 수집에 더해 public Google Sheets gviz JSON을 수집합니다.
  - `news`, `faculty` sheet row를 문서로 변환합니다.

## 파일 다운로드 정책

PDF나 문서 파일처럼 보이는 URL이라도 서버가 HTML fallback을 반환하면 파일로 저장하지 않습니다.

예를 들어 SPA 사이트에서는 존재하지 않는 `/something.pdf` 요청도 index HTML을 반환할 수 있습니다. 이런 응답을 PDF로 저장하면 RAG 데이터가 오염되므로, 현재 코드는 content-type과 PDF header를 확인한 뒤 실제 다운로드 파일만 `raw/<site>/files/`에 저장합니다.

## 검증 결과

2026-06-16 기준으로 아래 명령을 검증했습니다.

```powershell
python -m py_compile kaist_crawler\__main__.py kaist_crawler\__init__.py kaist_crawler\models.py kaist_crawler\config.py kaist_crawler\http_client.py kaist_crawler\store.py kaist_crawler\extractors.py kaist_crawler\vector_store.py kaist_crawler\adapters.py kaist_crawler\pipeline.py kaist_crawler\cli.py
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data_verified --skip-vector
python -m kaist_crawler build-vector --input data_verified\processed\chunks.jsonl --output data_verified
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data_run_default --source kaist_ai_systems
```

전체 6개 사이트 raw-only 수집 결과는 다음과 같았습니다.

- raw 파일: 184개
- 실제 PDF 다운로드: 17개
- source manifest: 6개
- 수집 중 비치명적 오류: 0개
- `processed/`, `vector/`: raw-only 실행에서는 생성하지 않음

## 한글 깨짐 확인

Markdown 파일은 UTF-8로 저장되어 있습니다. 파일 자체에는 mojibake 문자가 없고, PowerShell `Get-Content` 출력에서만 한글이 깨져 보일 수 있습니다.

파일 자체가 정상인지 확인하려면 Python으로 읽는 것이 가장 확실합니다.

```powershell
python -c "from pathlib import Path; print(Path('README.md').read_text(encoding='utf-8')[:200])"
```

PowerShell 출력이 계속 깨져 보이면 현재 세션에서 UTF-8 출력으로 바꾼 뒤 다시 확인합니다.

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
```

## 현재 한계와 다음 개선

- 현재 SPA adapter는 브라우저 렌더링을 실행하지 않습니다. AIC/AX의 route별 실제 렌더링 DOM 텍스트까지 고품질로 수집하려면 Playwright를 추가하는 것이 다음 단계입니다.
- PDF 파일은 raw로 다운로드됩니다. PDF 본문 텍스트 추출은 `pypdf` 또는 `PyPDF2`가 설치되어 있을 때 자동으로 동작합니다.
- vector 생성은 `hash`와 `openai` provider를 모두 지원합니다. 운영용 RAG는 `--embedding-provider openai`로 생성하는 것을 권장합니다.
