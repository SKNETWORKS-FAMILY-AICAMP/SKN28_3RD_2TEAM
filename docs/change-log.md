# 변경 기록

이 문서는 긴 작업 로그가 아니라, 프로젝트 구조와 RAG 품질에 영향을 준 변경만 요약한다.

기록 기준:
- 무엇을 바꿨는가
- 왜 바꿨는가
- 바꾼 뒤 무엇이 개선됐는가

## 2026-06-18

### 1. 크롤링 증분 수집 개선

무엇을 바꿨는가:
- 기존 raw manifest를 읽어 이미 수집한 URL은 다시 다운로드하지 않도록 했다.
- `raw_files_reused` 출력값을 추가했다.
- SPA route도 기존 raw가 있으면 Playwright 렌더링을 다시 하지 않게 했다.
- 달력 archive 경로(`/202605` 등)와 개인 홈 경로(`~user`)는 기본 추적 대상에서 제외했다.

왜 바꿨는가:
- 전체 사이트를 다시 수집할 때 시간이 오래 걸렸다.
- SPA 렌더링 실패나 불필요한 archive URL 때문에 raw error가 늘어났다.
- 다른 대학 사이트로 확장할 때 매번 전체 재수집하는 방식은 비효율적이다.

개선 결과:
- 전체 증분 raw 수집 시간이 약 `422.9초`에서 `80.4초`로 줄었다.
- 전체 증분 raw 수집 오류가 `16개`에서 `0개`로 줄었다.
- clean 없이 다시 실행하면 기존 raw를 재사용할 수 있다.

검증:
```text
python -B -m kaist_crawler raw --config configs\kaist_sources.yml --output data\kaist
result: raw_files_written=7 raw_files_reused=681 errors=0
```

### 2. raw 파일 수집 정책 개선

무엇을 바꿨는가:
- 파일 다운로드 판단에 URL뿐 아니라 링크 텍스트와 주변 문맥을 반영했다.
- 상담 RAG에 유용한 문맥은 유지하고, 세미나/뉴스레터/채용/기출 등 낮은 가치 문맥은 제외할 수 있게 했다.
- 사이트 분석기가 추천하는 crawl plan에도 같은 파일 정책을 포함했다.

왜 바꿨는가:
- PDF를 무조건 받으면 벡터스토어에 낮은 가치 문서가 많이 섞인다.
- 다른 대학원 사이트도 비슷하게 뉴스, 행사, 세미나, 기출 PDF가 섞일 가능성이 높다.

개선 결과:
- raw 단계에서 불필요한 파일 다운로드를 줄일 수 있다.
- 전처리와 벡터 저장 단계의 노이즈가 줄어든다.
- 파일 정책이 URL 패턴만 보던 방식보다 일반화됐다.

### 3. Hybrid relevance 문서 선별 추가

무엇을 바꿨는가:
- RAG에 넣을 문서와 제외할 문서를 `vector_candidate`로 표시하게 했다.
- 명확한 문서는 rule 기반으로 판단한다.
- 애매한 문서만 OpenAI LLM으로 판단할 수 있게 했다.
- LLM 판단 결과는 cache에 저장한다.

왜 바꿨는가:
- 전체 수집 데이터를 그대로 벡터스토어에 넣으면 상담 질문과 관련 없는 chunk가 검색될 수 있다.
- 모든 문서를 LLM으로 판단하면 비용과 시간이 커진다.

개선 결과:
- rule과 LLM을 섞어 비용을 줄이면서 후보 선별 품질을 높였다.
- 최종 처리 기준 `rule=1011`, `llm=250`으로 분담됐다.
- 벡터 후보 chunk는 `1335개`로 정리됐다.

검증:
```text
python -B -m kaist_crawler process --config configs\kaist_sources.yml --output data\kaist --clean --use-llm-relevance
result: documents=1261 chunks=2806 vector_candidates=1335 errors=5 filtered=2764 relevance_sources={'rule': 1011, 'llm': 250}
```

### 4. Chroma 벡터 저장 후보 필터링

무엇을 바꿨는가:
- `build-vector`는 기본적으로 `vector_candidate=false`인 chunk를 저장하지 않게 했다.
- 필요하면 `--include-non-candidates`로 전체 chunk 저장도 가능하게 했다.

왜 바꿨는가:
- 벡터스토어에 낮은 가치 chunk가 많으면 검색 품질이 떨어진다.
- 테스트 목적과 실제 RAG 목적의 저장 기준을 분리할 필요가 있었다.

개선 결과:
- 상담 RAG에 필요한 chunk 중심으로 벡터스토어를 만들 수 있다.
- 낮은 가치 문서를 raw/processed에는 남기되, vector DB에는 넣지 않는 구조가 됐다.

### 5. 품질 게이트 개선

무엇을 바꿨는가:
- 품질 리포트에 `vector_candidate_chunks`를 추가했다.
- 사이트별 vector candidate 비율을 확인할 수 있게 했다.
- `False` metadata가 `MISSING`으로 잘못 집계되던 문제를 수정했다.

왜 바꿨는가:
- 단순 documents/chunks 개수만으로는 RAG에 실제 저장될 데이터 품질을 판단하기 어렵다.

개선 결과:
- 수집량과 벡터 후보량을 분리해서 볼 수 있다.
- 사이트별로 노이즈가 많은 곳을 더 쉽게 찾을 수 있다.

현재 상태:
```text
quality_status=warn
quality_score=60
```

남은 이유:
- `kaist_mathsci`의 오래된/스캔 PDF 비중이 높다.
- PDF 5개는 텍스트 추출이 되지 않는다.

### 6. 코드 구조 리팩토링

무엇을 바꿨는가:
- 링크 발견 로직을 `link_discovery.py`로 분리했다.
- raw manifest 인덱싱을 `raw_manifest.py`로 분리했다.
- relevance 타입과 rule을 `relevance_types.py`, `relevance_rules.py`로 분리했다.
- `processor.py`의 raw record 처리 루프를 함수 단위로 나눴다.
- `cli.py`는 새 파일을 만들지 않고 내부 handler 함수로 분리했다.

왜 바꿨는가:
- 크롤링, 전처리, relevance 판단이 커지면서 한 함수나 한 파일에 책임이 몰렸다.
- 다른 대학원 사이트로 확장할 때 같은 로직을 재사용하기 쉽게 만들 필요가 있었다.
- 다만 파일 수가 너무 늘어나는 것도 피해야 했다.

개선 결과:
- `main()`은 command dispatch만 담당한다.
- raw manifest, 링크 발견, relevance rule을 각각 독립적으로 테스트할 수 있다.
- 전체 테스트가 `52개`로 늘었고 모두 통과한다.

검증:
```text
python -B -m unittest discover -s tests
result: 52 tests OK
```

## 현재 남은 이슈

### 1. 수학과 PDF 텍스트 추출 실패

현상:
- `kaist_mathsci` PDF 5개가 텍스트 추출되지 않는다.

원인:
- 스캔 PDF 또는 malformed PDF일 가능성이 높다.

대응:
- 지금은 RAG 핵심 품질에 큰 영향을 주지 않으므로 보류한다.
- 필요하면 OCR 단계를 별도 전처리 옵션으로 추가한다.

### 2. `adapters.py`가 아직 크다

현상:
- static HTML, SPA, Google Sheets 기반 SPA adapter가 한 파일에 있다.

판단:
- 지금 당장 새 파일을 더 늘릴 필요는 없다.
- 실제로 새 adapter가 추가되거나 유지보수가 어려워질 때 분리한다.

### 3. 다음 우선순위

수집/전처리 구조는 현재 단계에서 충분히 동작한다.

다음 작업은 리팩토링보다 아래 순서가 더 중요하다:
1. Chroma vector store 생성
2. 대표 상담 질문 retrieval 평가
3. 검색 실패 사례 기반 전처리/필터 개선
4. 다른 대학원 사이트 추가 수집 실험
