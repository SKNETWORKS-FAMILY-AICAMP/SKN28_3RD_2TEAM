# KAIST 통합 저장 및 크롤링 전략

작성일: 2026-06-17

## 기준

AI 대학과 자연과학대학은 별도 프로젝트가 아니라 KAIST 내부 source group으로 본다.

통합 기준:

- `institution=kaist`
- AI 대학: `college=ai`
- 자연과학대학: `college=natural_sciences`
- 통합 config: `configs/kaist_sources.yml`
- 통합 출력 루트: `data/kaist`

개별 config는 실험이나 부분 재수집용으로 유지한다.

- `configs/kaist_ai_sources.yml`
- `configs/kaist_natural_sciences_sources.yml`

## 통합 명령

raw 수집:

```powershell
python -m kaist_crawler raw --config configs\kaist_sources.yml --output data\kaist --clean
```

전처리:

```powershell
python -m kaist_crawler process --config configs\kaist_sources.yml --output data\kaist --clean
```

Quality Gate:

```powershell
python -m kaist_crawler quality-gate --config configs\kaist_sources.yml --output data\kaist
```

벡터 저장:

```powershell
python -m kaist_crawler build-vector --input data\kaist\processed\chunks.jsonl --output data\kaist --embedding-provider openai
```

## 현재 통합 데이터 상태

기존 AI raw와 자연과학 raw를 `data/kaist/raw`로 통합했고, manifest의 `raw_path`도 `data/kaist/raw/...` 기준으로 정규화했다.

전처리 결과:

```text
documents=942
chunks=2080
errors=4
filtered=2488
```

metadata 분포:

```text
institution:
  kaist=2080

college:
  ai=185
  natural_sciences=1895
```

dept 분포:

```text
aic=40
ai_systems=33
ax=18
fx=50
kaist=44
natsci=161
physics=193
mathsci=1243
chem=152
quantum=146
```

Quality Gate:

```text
status=fail
score=30
```

실패 원인:

- `kaist_ai_college`가 현재 chunk 0개이다.
- 나머지 source는 대부분 `pass`, 수리과학과는 PDF 비중 때문에 `warn`이다.

## 전략

KAIST 내부 사이트를 추가할 때는 새 config를 따로 운영하지 않고 `configs/kaist_sources.yml`에 source를 추가한다.

필수 metadata:

```yaml
institution: kaist
institution_name: KAIST
college: <college_code>
college_name: <college_name>
```

이 metadata는 전처리 문서와 chunk에 그대로 들어가며, Chroma metadata filter에서 다음처럼 사용할 수 있다.

- KAIST 전체 검색: `institution=kaist`
- AI 대학만 검색: `college=ai`
- 자연과학대학만 검색: `college=natural_sciences`
- 특정 학과 검색: `dept=physics`, `dept=chem`, `dept=aic` 등

## 남은 작업

- AI College SPA 수집 공백 해결
- 수리과학과 PDF 필터 강화
- `content_subtype`과 `vector_candidate` 추가
- 통합 `data/kaist` 기준으로 OpenAI embedding Chroma 재생성
