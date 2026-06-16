# KAIST AI 대학원 크롤러

KAIST AI 관련 학과 사이트와 KAIST 본원/AI College 사이트를 수집해서 RAG 챗봇에 사용할 raw data, processed documents/chunks, vector store를 만드는 Python 프로젝트입니다.

현재 수집 대상은 다음 6개 사이트입니다.

- `https://aic.kaist.ac.kr/`
- `https://ai-systems.kaist.ac.kr/`
- `https://ax.kaist.ac.kr/`
- `https://fx.kaist.ac.kr/`
- `https://www.kaist.ac.kr/kr/`
- `https://aicollege.kaist.ac.kr/`

프로젝트 위치는 `C:\Users\Playdata\workspace\kaist_ai_crawler_project`입니다.

## 설치

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## 실행 흐름

현재 파이프라인은 역할을 분리합니다.

```text
raw 수집 -> raw manifest 기반 전처리 -> vector store 생성
```

raw data만 수집합니다. PDF는 원본 파일만 저장하고 텍스트 추출은 하지 않습니다.

```powershell
python -m kaist_crawler raw --config configs\kaist_ai_sources.yml --output data
```

이미 수집된 raw data에서 documents/chunks를 생성합니다. PDF 텍스트 추출은 이 단계에서 수행됩니다.

```powershell
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data
```

raw 수집, 전처리, vector store 생성을 한 번에 실행합니다.

```powershell
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data
```

특정 사이트만 실행할 수도 있습니다.

```powershell
python -m kaist_crawler raw --config configs\kaist_ai_sources.yml --output data --source kaist_ai_systems
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --source kaist_ai_systems
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data --source kaist_ai_systems --skip-vector
```

재수집 전에 command별 출력물을 지우려면 `--clean`을 사용합니다.

```powershell
python -m kaist_crawler raw --config configs\kaist_ai_sources.yml --output data --clean
python -m kaist_crawler process --config configs\kaist_ai_sources.yml --output data --clean
python -m kaist_crawler run --config configs\kaist_ai_sources.yml --output data --clean
```

`raw --clean`은 `raw/`만 지웁니다. `process --clean`은 `processed/`만 지웁니다. `run --clean`은 `raw/`, `processed/`, `vector/`를 지웁니다.

이미 만들어진 chunk 파일로 vector store만 다시 만들 수 있습니다.

```powershell
python -m kaist_crawler build-vector --input data\processed\chunks.jsonl --output data
```

OpenAI embedding을 사용하려면 `OPENAI_API_KEY`를 설정하고 `--embedding-provider openai`를 지정합니다.

```powershell
$env:OPENAI_API_KEY = "sk-..."
python -m kaist_crawler build-vector --input data\processed\chunks.jsonl --output data --embedding-provider openai
```

기본 OpenAI embedding 모델은 `text-embedding-3-large`입니다. 비용과 속도를 줄이려면 `--embedding-model text-embedding-3-small`을 사용할 수 있습니다.

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
    processor.py
    policies.py
    config.py
    http_client.py
    store.py
    extractors.py
    rendering.py
    vector_store.py
    models.py
  requirements.txt
  README.md
```

## 출력 구조

```text
data/
  raw/
    <site>/
      manifest.jsonl
      skipped_files.jsonl
      pages/
      assets/
      sheets/
      files/
  processed/
    documents.jsonl
    chunks.jsonl
    errors.jsonl
    filtered.jsonl
  vector/
    chroma/
```

- `raw/`: 원본 HTML, 렌더링 HTML, JS/CSS asset, Google Sheets JSON, PDF 파일을 저장합니다.
- `manifest.jsonl`: raw 파일의 URL, 저장 경로, content-type, sha256, metadata를 기록합니다.
- `skipped_files.jsonl`: raw 단계에서 file policy 때문에 다운로드하지 않은 파일과 제외 사유를 기록합니다.
- `processed/documents.jsonl`: raw data에서 추출한 문서 단위 텍스트입니다.
- `processed/chunks.jsonl`: vector store에 넣기 위한 chunk입니다.
- `processed/errors.jsonl`: 수집 또는 전처리 중 발생한 비치명적 오류입니다.
- `processed/filtered.jsonl`: 전처리 단계에서 벡터 저장 대상에서 제외한 raw/document/chunk와 사유입니다.
- `vector/chroma/`: Chroma 로컬 vector store입니다.

## 모듈 역할

- `adapters.py`: 사이트별 raw 수집만 담당합니다.
- `processor.py`: `raw/*/manifest.jsonl`을 읽어 documents/chunks를 생성합니다. PDF 텍스트 추출도 여기서 수행합니다.
- `policies.py`: raw 파일 다운로드 정책과 전처리 필터 정책을 정의합니다.
- `pipeline.py`: `raw`, `process`, `run`, `build-vector` 흐름을 조합합니다.
- `extractors.py`: HTML, JS literal, PDF, Google Sheets JSON, chunking 관련 순수 추출 함수를 제공합니다.
- `store.py`: raw 파일 저장과 manifest 기록을 담당합니다.
- `vector_store.py`: hash/OpenAI embedding과 Chroma 저장을 담당합니다.

## 수집 및 전처리 필터 정책

정책은 `configs/kaist_ai_sources.yml`에서 조정합니다. 다른 대학원 사이트를 추가할 때는 같은 기본 정책을 재사용하고, 사이트별로 필요한 범위만 override합니다.

- raw file policy: `max_file_size_mb`, `exclude_url_patterns`, `include_url_patterns`로 대용량 뉴스레터·매거진·연례보고서 같은 파일 다운로드를 사전에 제한합니다.
- processing filter policy: 중복 raw sha256, 중복 문서 텍스트, 중복 chunk, 너무 짧은 문서, HTML shell, 대용량/뉴스레터 PDF를 벡터 후보에서 제외합니다.
- KAIST 본원 사이트는 HTML 범위를 입학·교육 페이지 중심으로 좁혀, 학과 RAG와 관련성이 낮은 일반 홍보/캠퍼스/뉴스 페이지가 벡터 품질을 낮추지 않게 합니다.

## PDF 정책

PDF는 raw 단계에서 원본 파일만 저장합니다. 텍스트 추출은 `process` 또는 `run`의 processed 단계에서 수행합니다.

추출 순서:

1. `pymupdf`
2. `pdfplumber`
3. `pypdf`
4. `PyPDF2`

추출에 성공하면 PDF 문서는 `document_type=pdf`, `pdf_extractor`, `pdf_pages` metadata를 가집니다.

## SPA 렌더링 정책

SPA 사이트는 Playwright로 route별 rendered HTML 저장을 시도합니다.

- 기본 대기 전략: `domcontentloaded` 후 1초
- 첫 route 렌더링이 실패하면 나머지 route는 HTML shell fallback으로 저장
- raw 단계에서는 rendered HTML만 저장하고 DOM 텍스트 추출은 하지 않음
- processed 단계에서 raw HTML/JS asset을 읽어 텍스트를 추출

## 한글 깨짐 확인

Markdown 파일은 UTF-8로 저장합니다. PowerShell에서 한글이 깨져 보이면 터미널 출력 인코딩을 확인합니다.

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
```

파일 자체 확인은 Python으로 하는 것이 가장 확실합니다.

```powershell
python -c "from pathlib import Path; print(Path('README.md').read_text(encoding='utf-8')[:200])"
```
