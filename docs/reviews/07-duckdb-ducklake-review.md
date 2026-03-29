# DuckDB / DuckLake 리뷰

**리뷰어**: duckdb-reviewer
**리뷰 일자**: 2026-03-27
**수정 일자**: 2026-03-29 (DuckLake 전환 후)

---

## 리뷰 결과

### Critical (이전 3건) — 모두 해결됨

**C1. DuckLake가 파이프라인에 전혀 통합되지 않음 — Dead Infrastructure** ✅
- dlt ducklake destination으로 Bronze 적재
- dbt-duckdb가 DuckLake ATTACH하여 Silver/Gold 변환
- enrich_service가 DuckLake Silver 직접 읽기
- reverse_etl로 Gold → PostgreSQL serving sync
- **판정**: DuckLake가 파이프라인의 핵심 저장소로 작동

**C2. Bronze parquet의 소비자가 없음 — Dead Data** ✅
- dbt Bronze view(`stg_articles.sql`)가 `lake.bronze.articles` source로 사용
- 전체 소비 체인: dlt Bronze → dbt Silver → AI Enrich → dbt Gold → reverse_etl → PG serving

**C3. `devworld-lake` 버킷 미생성** ✅
- `docker-compose.yml` minio-init에 `mc mb --ignore-existing local/devworld-lake` 추가
- 5개 버킷 모두 생성: raw, bronze, lake, silver, gold-analytics

### Warning (이전 5건 + 신규 3건)

**W1: setup.py와 duckdb-ui.py 연결 방식 불일치** ✅
- 둘 다 `ATTACH ... AS lake (TYPE ducklake, DATA_PATH ...)` 패턴 사용

**W2: dbt-duckdb 패키지 미사용** ✅
- dbt-duckdb가 이제 활성 dbt adapter

**W3: DuckDB/DuckLake 버전 호환성 우려** 🔄
- DuckLake가 아직 젊은 extension이므로 리스크 잔존

**W4: silver/gold-analytics 버킷 미사용** 🔄
- `devworld-silver`, `devworld-gold-analytics` 버킷은 생성되었으나 DuckLake DATA_PATH와 무관
- DuckLake가 모든 데이터를 `s3://devworld-bronze`에 저장

**W5: DuckLake catalog DSN 다르게 정의** ✅ (부분)
- 파이프라인 전체에서 `airflow_db` 일관 참조. config.py의 `localhost` 기본값만 차이 (로컬 개발용)

**W6. 🆕 DATA_PATH 불일치 (devworld-bronze vs devworld-lake)**
- config.py/docker-compose: `s3://devworld-bronze`, duckdb-ui: `s3://devworld-lake`
- 파이프라인과 분석 도구가 다른 버킷을 참조할 수 있음

**W7. 🆕 enrich_service.py DuckLake 연결 코드 중복**
- `enrich_service.py`의 `_connect_ducklake()`가 `setup.py`의 `create_ducklake_connection()`과 동일 로직

**W8. 🆕 DuckDB f-string SQL injection 위험**
- `enrich_service.py`, `setup.py`, `duckdb-ui.py`에서 config 값을 f-string으로 SQL에 직접 삽입
- config/env 값이므로 외부 입력은 아니지만, 비밀번호에 작은따옴표 포함 시 SQL 깨짐

### Pass (이전 3건 + 신규)

- CLAUDE.md의 DuckDB/DuckLake 역할 정의 정확 (업데이트됨)
- Makefile duckdb-ui 타겟
- DuckLake가 파이프라인의 load-bearing 컴포넌트로 정상 작동
- dbt-duckdb + DuckLake attach + postgres attach 구성 적절

---

## 핵심 판단

> 이전 리뷰: "DuckLake는 설계는 되었으나 구현이 중단된 상태"
> **현재: DuckLake는 파이프라인의 핵심 저장소로 완전 통합.** 이전 "즉시 제거" 권고는 무효.

## 이전 권고 vs 현재 상태

| 이전 권고 | 현재 상태 |
|---|---|
| ducklake 패키지 즉시 제거 | ✅ 활성 사용 (dlt destination) |
| dbt-duckdb 패키지 즉시 제거 | ✅ 활성 사용 (dbt adapter) |
| src/infrastructure/ducklake/ 제거 | ✅ `create_ducklake_connection()` 유틸리티로 재작성 |
| DUCKLAKE_CATALOG_URL 제거 | ✅ 활성 사용 (파이프라인 전체) |
| StorageConfig.lake_bucket 제거 | ✅ 유지 (devworld-lake 버킷 생성됨) |
| dbt-duckdb 전환 권고하지 않음 | ✅ 전환 완료, reverse_etl로 FTS 해결 |
