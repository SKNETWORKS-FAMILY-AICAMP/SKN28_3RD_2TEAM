# 자연과학대학 사이트 수집 품질 평가

작성일: 2026-06-17

## 대상 사이트

- `https://natsci.kaist.ac.kr`
- `https://physics.kaist.ac.kr`
- `https://mathsci.kaist.ac.kr/home/`
- `https://chem.kaist.ac.kr/main/`
- `https://quantum.kaist.ac.kr/`

## 분류 결과

| source_id | 추천 adapter | 판정 | confidence | 비고 |
| --- | --- | --- | --- | --- |
| `kaist_natsci` | `static_html` | 정적 HTML | 0.87 | sitemap 정상 |
| `kaist_physics` | `static_html` | 정적 HTML | 0.87 | `index.php?mid=...` query 기반 메뉴 |
| `kaist_mathsci` | `static_html` | 정적 HTML | 0.87 | WordPress 계열, PDF 다수 |
| `kaist_chem` | `static_html` | 정적 HTML | 0.87 | extensionless route 다수 |
| `kaist_quantum` | `static_html` | 정적 HTML | 0.58 | 초기 route 후보는 적지만 링크 추적으로 수집 가능 |

## 수집 결과

출력 위치:

```text
data/natural_sciences/
```

raw manifest unique 기준:

| site | unique raw | pages | files |
| --- | ---: | ---: | ---: |
| `kaist_natsci` | 70 | 70 | 0 |
| `kaist_physics` | 80 | 80 | 0 |
| `kaist_mathsci` | 195 | 78 | 117 |
| `kaist_chem` | 79 | 79 | 0 |
| `kaist_quantum` | 67 | 67 | 0 |
| 합계 | 491 | 374 | 117 |

전처리 결과:

```text
documents=808
chunks=1895
errors=7
filtered=1574
```

chunk 분포:

| site | chunks |
| --- | ---: |
| `kaist_natsci` | 161 |
| `kaist_physics` | 193 |
| `kaist_mathsci` | 1243 |
| `kaist_chem` | 152 |
| `kaist_quantum` | 146 |

source type:

| source_type | chunks |
| --- | ---: |
| `html` | 896 |
| `pdf` | 999 |

content type:

| content_type | chunks |
| --- | ---: |
| `general` | 495 |
| `admission` | 440 |
| `event` | 420 |
| `person` | 287 |
| `course` | 168 |
| `department_profile` | 53 |
| `office_contact` | 19 |
| `requirement` | 7 |
| `scholarship` | 6 |

dept metadata:

| dept | chunks |
| --- | ---: |
| `natsci` | 161 |
| `physics` | 193 |
| `mathsci` | 1243 |
| `chem` | 152 |
| `quantum` | 146 |

## 평가

전체적으로 자연과학대학 계열 사이트는 SPA가 아니라 정적 HTML 중심이라 현재 crawler adapter와 잘 맞는다. 다만 실제 사이트 구조가 KAIST AI 사이트와 달라 두 가지 crawler 개선이 필요했고 반영했다.

- extensionless URL 추적: `/faculty`, `/notice`, `/curriculum` 같은 경로를 따라가도록 개선했다.
- query 기반 URL 추적: 물리학과의 `index.php?mid=...`, `index.php?document_srl=...` 페이지를 따라가도록 개선했다.

품질이 좋은 데이터:

- 화학과: 교수진, 대학원과정, 교과목, 연구성과가 HTML 본문으로 잘 수집된다.
- 양자대학원: 교수진, 연구팀, 커뮤니티/입학 공지가 잘 수집된다.
- 물리학과: query 기반 링크 추적 개선 후 root 1페이지 수준에서 80개 page로 확장됐다.
- 자연과학대학 본부: 학과 소개, 연구사업, 공지/뉴스가 수집된다.

품질 주의 데이터:

- 수리과학과는 PDF가 많고, 이 중 일부는 이미지 기반 PDF라 텍스트 추출이 실패한다.
- 수리과학과 PDF에는 연구 하이라이트, 과거 시험, 자격시험 자료가 섞여 있어 RAG 목적에 따라 필터링이 필요하다.
- `general` chunk가 495개로 많다. 연구비 표, 오시는 길, 통계성 페이지 등은 질문 유형에 따라 RAG 품질을 낮출 수 있다.
- raw 단계에서 오래된 첨부파일 endpoint, PDF viewer URL, 권한 제한 파일로 403/404가 다수 발생했다. 치명적 오류는 아니지만 file policy 보강 후보이다.

## 권장 후속 개선

1. 수리과학과 PDF 필터 강화
   - `oldexam`, 과거 시험, 이미지 기반 PDF는 기본 vector 후보에서 제외하는 정책을 추가한다.
   - PDF viewer URL의 `file=` 파라미터에서 실제 PDF URL을 추출하는 로직을 추가한다.

2. content type 세분화
   - `event`와 `person`으로 과분류되는 연구성과/뉴스를 `research_highlight`, `notice`, `seminar` 등으로 나눈다.
   - `general` 중 오시는 길, 연구비 통계, 단순 조직/표 페이지는 RAG 저장 전 필터링 후보로 표시한다.

3. metadata 확장
   - 새 source는 기본적으로 source id 기반 `dept`를 갖도록 수정했다.
   - 다음 단계에서는 `college=natsci`, `program_level=graduate/undergraduate`, `content_subtype`을 추가하면 metadata filter 검색 품질이 좋아진다.

4. 벡터 저장 전 평가
   - 현재 데이터는 그대로 Chroma에 넣을 수 있지만, 수리과학 PDF와 `general` chunk 때문에 먼저 전처리 필터를 한 번 더 개선하는 것이 좋다.
