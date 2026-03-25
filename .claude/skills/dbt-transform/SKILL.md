---
name: dbt-transform
description: dbt로 Bronze → Silver → Gold 데이터 변환 모델 작성
disable-model-invocation: true
argument-hint: "<model_name>"
---

$ARGUMENTS dbt 모델을 작성하거나 수정한다.

## 데이터 레이어

```
Bronze (parquet, MinIO)  → dbt → Silver (parquet, MinIO)
                                → Gold Analytics (parquet, MinIO)
                                → Gold Serving (table, PostgreSQL)
```

## 엔진 구성

### DuckDB + DuckLake
- DuckDB: ETL 컨테이너 내부 분석 엔진 (상주 서버 아님)
- DuckLake catalog: PostgreSQL에 메타데이터 저장
- DuckLake storage: MinIO/R2에 parquet 저장
- dbt-duckdb adapter 사용

### dbt profiles.yml
- dev: DuckDB + httpfs → MinIO parquet 읽기/쓰기
- prod: DuckDB + httpfs → R2 parquet 읽기/쓰기 + PostgreSQL (Gold Serving)

## 모델 규칙

### Bronze (models/bronze/)
- materialized: view (source 위의 thin layer)
- 역할: type casting, column renaming만
- source: DuckLake의 Bronze parquet
- 접두사: `stg_`

### Silver (models/silver/)
- materialized: table (parquet on MinIO)
- 역할: 정제, dedup (content_hash 기반), null 필터링
- ref: Bronze 모델 참조
- 접두사: `int_`

### Gold (models/gold/)
- materialized: table
- Gold Analytics: parquet on MinIO (분석/통계용)
- Gold Serving: PostgreSQL table (API 서빙용)
- ref: Silver 모델 참조
- 접두사: `mart_`

### schema.yml
- 모든 레이어에 schema.yml 필수
- column tests: unique, not_null (적절한 컬럼에)
- source 정의: DuckLake에서 읽는 Bronze 테이블

## 하지 말 것
- dbt에서 raw crawling이나 HTML parsing을 하지 않는다
- Bronze/Silver를 PostgreSQL에 넣지 않는다
- DuckDB/DuckLake를 서비스 DB 대체재로 쓰지 않는다
- Gold를 aggregation-only로 취급하지 않는다 (아티클 단위 서빙도 Gold)

## 검증
- `dbt run` 성공
- `dbt test` 통과
- MinIO에서 Silver/Gold parquet 확인
- PostgreSQL에서 Gold Serving 테이블 확인
