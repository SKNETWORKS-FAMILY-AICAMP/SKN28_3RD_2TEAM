# 사이트 프로파일링, 수집 계획, 품질 게이트 구조

작성일: 2026-06-17

## 목표

최종 목표는 대학원 URL만 넣었을 때 RAG에 필요한 데이터를 자동으로 수집하고, 벡터 저장 전에 품질이 낮은 데이터를 걸러내는 것이다.

현재 구조는 다음 순서로 동작하도록 설계한다.

```text
URL 입력
-> SiteProfile 생성
-> CrawlPlan 생성
-> raw 수집
-> 전처리
-> Quality Gate 평가
-> 벡터 저장 후보 확정
```

## SiteProfile

`SiteProfile`은 사이트가 어떤 구조인지 기록한다.

주요 필드:

- `site_type`: `static_html`, `spa`, `spa_with_google_sheets`
- `adapter`: 현재 사용할 crawler adapter
- `cms_type`: `generic`, `wordpress`, `xe_php_board`, `gnuboard`, `pdf_viewer_site` 등
- `url_patterns`: `extensionless_routes`, `query_routes`, `xe_php_board_query`, `pdf_viewer_urls` 등
- `route_candidates`: 수집 시작 route 후보
- `file_candidates`: 첨부파일 후보
- `robots_status`, `sitemap_status`
- `risks`: 수집 전 확인해야 할 위험 신호

이 단계는 수집을 실행하지 않고, 사이트 구조와 위험을 먼저 파악하기 위한 단계이다.

## CrawlPlan

`CrawlPlan`은 실제 수집에 사용할 계획이다.

주요 필드:

- `routes`: seed route 목록
- `known_files`: 직접 다운로드할 파일 후보
- `raw_options`: adapter별 수집 옵션
- `processing_options`: 전처리 필터 옵션
- `route_policy`: query 보존, 제외 경로, 확장자 규칙
- `file_policy`: 다운로드 전 파일 필터
- `priority_sections`: RAG에서 우선시할 정보 유형

예를 들어 물리학과처럼 `index.php?mid=...` 구조를 쓰는 사이트는 `route_policy.preserve_query_for`에 `mid`, `document_srl`이 들어간다.

수리과학과처럼 PDF viewer와 과거 시험 PDF가 많은 사이트는 `file_policy.exclude_url_patterns`와 `processing.filter_policy.exclude_pdf_url_patterns`에 `oldexam`, `viewer.php`, `pdfjs-viewer`, `기출` 같은 패턴이 들어간다.

## Quality Gate

`Quality Gate`는 전처리 결과가 벡터 저장에 적합한지 평가한다.

생성 파일:

```text
processed/quality_gate.json
processed/quality_gate.md
```

평가 기준:

- chunk가 생성됐는지
- `dept` metadata가 빠졌는지
- `general` chunk 비율이 과도한지
- PDF chunk 비율이 과도한지
- PDF 텍스트 추출 오류가 있는지
- 짧은 문서가 과도하게 필터링됐는지

결과는 `pass`, `warn`, `fail` 중 하나이다.

- `pass`: 벡터 저장 가능
- `warn`: 벡터 저장 전 필터/전처리 검토 권장
- `fail`: 바로 벡터 저장하면 RAG 품질 저하 가능성이 큼

## 명령어

사이트 분석:

```powershell
python -m kaist_crawler analyze-site https://example.edu/graduate --id example_grad --name "Example Graduate School" --output configs\analysis_example.yml
```

전처리 후 품질 게이트 재생성:

```powershell
python -m kaist_crawler quality-gate --config configs\example_sources.yml --output data\example
```

수집과 전처리:

```powershell
python -m kaist_crawler raw --config configs\example_sources.yml --output data\example --clean
python -m kaist_crawler process --config configs\example_sources.yml --output data\example --clean
```

`process` 명령은 자동으로 `quality_gate.json`과 `quality_gate.md`를 생성한다.

## 현재 한계

- SiteProfile은 아직 완전한 CMS 자동 인식기가 아니다. WordPress, XE/PHP board, query route, PDF viewer 패턴을 우선 지원한다.
- CrawlPlan은 정책 초안을 만든다. 처음 보는 사이트는 제한 수집 후 Quality Gate를 보고 정책을 보정해야 한다.
- Quality Gate는 규칙 기반이다. 다음 단계에서는 `old_exam`, `research_highlight`, `seminar`, `notice` 같은 `content_subtype`을 추가해야 더 정밀해진다.
