# KAIST AI대학 데이터 — MySQL 적재 가이드

KAIST AI대학 4개 학과(AIC·AX·AI Systems·FX) 크롤링 데이터를 MySQL에 적재하는 SQL 스크립트 모음입니다.

---

## 파일 구성

| 파일 | 역할 |
|------|------|
| `01_schema.sql` | DB·테이블 생성 (스키마 정의, PK/FK/INDEX) |
| `02_load.sql` | CSV → 스테이징 → 정규화 테이블 적재 (ETL) |
| `03_verify.sql` | 적재 결과 검증 쿼리 모음 |
| `ERD.md` | 개체-관계 다이어그램 (Mermaid) |
| `clean_csv.ps1` | 원본 CSV 내부 줄바꿈 제거 → `csv/_clean/` 생성 |

실행 순서: `01` → `02` → `03`

---

## 설계 원칙 (요약)

자세한 다이어그램·설명은 [`ERD.md`](ERD.md) 참고. 핵심만 요약하면:

- **주제 영역 3분할** — ① 업무 도메인(department·person·course·track·course_track·admission·event) ② 수집/자원(asset·attachment) ③ RAG(rag_document·rag_chunk). ERD도 영역별 도표로 나눠 발표 자료에 담기 쉽게 했습니다.
- **키 전략 통일** — 크롤링이 준 고유 ID가 있으면 자연키 PK(VARCHAR: `record_id`/`doc_id`/`chunk_id`), 없는 파생 엔터티만 인조키(`BIGINT AUTO_INCREMENT`: `track_id`/`attachment_id`) + `UNIQUE` 로 업무 고유성 보장.
- **정규화(3NF)** — `dept_name` 을 `department` 한 곳으로 모으고, `rag_chunk` 의 문서 메타(dept·title·source_url 등 6컬럼, 523행 전수 중복)는 `rag_document` 와 이행적 종속이라 제거. 학과·제목은 `doc_id` 로 JOIN 해서 얻습니다.
- **참조 명확화** — `attachment` 의 실제 부모는 게시글(post)이며 `board` 로 admission/event 가 갈립니다(`(dept,board,post_id)` UNIQUE 로 식별). 교수↔과목 M:N 은 크롤링 데이터에 연결 정보가 없어 **데이터 갭**으로 남겨두었습니다.

---

## 환경 설정

### 요구사항
- MySQL 8.x (서비스 실행 중)
- 저장소를 **어느 경로에 클론해도 무관**합니다. 단, 실행은 반드시 **프로젝트 루트(저장소 최상위 폴더)에서** 해야 합니다.

> `02_load.sql`의 CSV 경로는 프로젝트 루트 기준 **상대경로**(`csv/_clean/...`)로 작성되어 있어, 팀원이 경로를 별도 수정할 필요가 없습니다.

### MySQL 권한 설정 (root로 1회 실행)

아래 `'your_user'`를 **본인 MySQL 계정명**으로 바꿔서 실행하세요.

```sql
-- kaist_ai DB 및 LOAD DATA 권한 부여
GRANT ALL PRIVILEGES ON kaist_ai.* TO 'your_user'@'localhost';
GRANT FILE ON *.* TO 'your_user'@'localhost';
FLUSH PRIVILEGES;

-- LOAD DATA LOCAL INFILE 서버 측 활성화
SET GLOBAL local_infile = 1;
```

> 예) 계정이 `root`이면 `'root'@'localhost'`, `practice`이면 `'practice'@'localhost'`

---

## 실행 명령어

**반드시 프로젝트 루트로 먼저 이동한 뒤** 실행하세요. `-u` 뒤에 본인 계정, `-p` 뒤에 본인 비밀번호를 붙입니다.

```bash
# 0단계: 프로젝트 루트로 이동 (각자 클론한 경로로 변경)
cd /path/to/skn28-3RD-2TEAM

# 1단계: 테이블 생성
mysql -u your_user -pyour_password --local-infile=1 -e "source sql/01_schema.sql"

# 2단계: 데이터 적재
mysql -u your_user -pyour_password --local-infile=1 -e "source sql/02_load.sql"

# 3단계: 검증
mysql -u your_user -pyour_password --local-infile=1 -e "source sql/03_verify.sql"
```

> - `-p` 바로 뒤에 비밀번호를 붙입니다 (띄어쓰기 없음). 예: `-proot1234`
> - `--local-infile=1` 플래그 없이 실행하면 `02_load.sql`의 `LOAD DATA LOCAL INFILE`이 실패합니다.
> - Windows에서 `mysql`을 찾지 못하면 전체 경로로 실행하세요: `"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"`

---

## CSV 전처리 (원본 CSV 수정 시에만)

`csv/_clean/`은 이미 저장소에 포함되어 있어 **별도 실행 없이 바로 SQL을 실행할 수 있습니다.**

원본 `csv/` 파일을 수정했을 때만 아래 스크립트로 `_clean/`을 재생성하세요.

```powershell
# PowerShell에서 실행 (프로젝트 루트 기준)
.\sql\clean_csv.ps1
```

---

## 적재 후 기대 행 수

| 테이블 | 행 수 | 비고 |
|--------|-------|------|
| department | 4 | 학과 마스터 |
| person | 246 | 교수/구성원 |
| course | 109 | 교과목 |
| track | 21 | 트랙 마스터 (자동 추출) |
| course_track | 109 | 과목↔트랙 교차 엔터티 |
| admission | 74 | 입학 정보 |
| event | 4 | 행사 |
| asset | 270 | 링크·이미지 (원본 494행, 중복 224행 제거) |
| attachment | 4 | PDF 첨부파일 |
| rag_document | 482 | 문서 메타데이터 |
| rag_chunk | 523 | RAG 검색용 청크 (문서 메타는 rag_document 에서 JOIN) |
| quality_report | 14 | 검산 지표 (독립 테이블) |

---

## ERD 미리보기

VS Code에서 `ERD.md`를 열고 `Ctrl+Shift+V`로 Markdown Preview를 열면 Mermaid 다이어그램을 볼 수 있습니다.  
(Mermaid 미리보기 확장 설치 필요)
