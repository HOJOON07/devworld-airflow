# DuckDB / DuckLake 리뷰

**리뷰어**: duckdb-reviewer
**리뷰 일자**: 2026-03-27

---

## 리뷰 결과

### Critical (3건)

**C1. DuckLake가 파이프라인에 전혀 통합되지 않음 — Dead Infrastructure**
- setup.py 작성됨, 미사용 (어떤 DAG에서도 import 안 함)
- DuckLake catalog 미초기화, 테이블 미등록

**C2. Bronze parquet의 소비자가 없음 — Dead Data**
- dlt가 매일 parquet 적재 → dbt 안 읽음 → DuckLake 안 읽음
- 유일한 소비 가능 경로: duckdb-ui.py (read_parquet)

**C3. `devworld-lake` 버킷 미생성**
- config에만 존재, minio-init 미포함
- setup.py와 duckdb-ui.py가 서로 다른 버킷(lake vs bronze) 참조

### Warning (5건)

- W1: setup.py와 duckdb-ui.py의 DuckLake 연결 방식 불일치
- W2: dbt-duckdb 패키지 설치됨 but 미사용
- W3: DuckDB/DuckLake 버전 호환성 우려
- W4: silver/gold-analytics 버킷 미사용
- W5: DuckLake catalog DSN이 3곳에 다르게 정의

### Pass (3건)

- CLAUDE.md의 DuckDB/DuckLake 역할 정의 명확
- "하지 말 것" 가드레일 올바름
- Makefile duckdb-ui 타겟

---

## 핵심 판단

> DuckLake는 **"설계는 되었으나 구현이 중단된" 상태**.
> 현재 파이프라인에서 어떤 가치도 제공하지 않음.

## 통합되지 못한 이유 (추정)

1. PostgreSQL이 이미 충분했음
2. dbt-duckdb → dbt-postgres 전환 (FTS 때문)
3. DuckLake 자체 성숙도 이슈
4. Bronze parquet이 소비 경로 없이 선행됨

## 최종 권고: 단계적 정리

### 즉시 제거
- `ducklake` 패키지, `dbt-duckdb` 패키지
- `src/infrastructure/ducklake/` 디렉토리
- `DUCKLAKE_CATALOG_URL` 환경변수
- DuckLake 관련 connection/variable
- `StorageConfig.lake_bucket`

### 유지
- `duckdb` 패키지 (분석용)
- `duckdb-ui.py` (DuckLake 코드 제거, httpfs + read_parquet만)
- `make duckdb-ui`

### 판단 보류
- Bronze parquet 적재 (dlt_load DAG) — 보험으로서 가치, 소비 경로 검증 필요
- silver/gold-analytics 버킷 — 미래 placeholder

## dbt-duckdb 전환 판단

**전환 권고하지 않음.**
- PostgreSQL FTS (tsvector, GIN) 사용 불가
- Gold Serving이 PostgreSQL이어야 하는 요구사항과 충돌
- dbt-duckdb는 Gold Analytics 전용 별도 프로젝트로만 실익
