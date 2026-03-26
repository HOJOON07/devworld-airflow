---
name: dbt-transform
description: dbt로 Bronze → Silver → Gold 데이터 변환 모델 작성
disable-model-invocation: true
argument-hint: "<model_name>"
---

$ARGUMENTS dbt 모델을 작성하거나 수정한다.

## 데이터 레이어

```
PostgreSQL articles/crawl_sources → dbt → Bronze view (schema: bronze)
                                       → Silver table (schema: public)
                                       → Gold table (schema: public)
```

## 엔진 구성

### PostgreSQL (dbt adapter)
- dbt-postgres adapter 사용
- 모든 dbt 모델이 PostgreSQL에서 실행
- DuckDB/DuckLake는 dbt 경로에서 사용하지 않음 (분석 전용)

### dbt profiles.yml
- dev/prod 모두 PostgreSQL type
- dbname: app_db, schema: public
- Airflow에서는 Astronomer Cosmos + `postgres_app` connection으로 실행

### Astronomer Cosmos
- dbt DAG를 Airflow 태스크로 렌더링
- `PostgresUserPasswordProfileMapping` 사용
- 모델 단위 관측성 및 재시도

## 모델 규칙

### Bronze (models/bronze/)
- materialized: view
- schema: bronze
- 역할: PostgreSQL source 테이블 위의 thin layer (JOIN, column alias)
- source: `{{ source('public', 'articles') }}`, `{{ source('public', 'crawl_sources') }}`
- 접두사: `stg_`

### Silver (models/silver/)
- materialized: table
- schema: public
- 역할: 정제, dedup (content_hash 기반 row_number), null 필터링
- ref: Bronze 모델 참조
- 접두사: `int_`

### Gold (models/gold/)
- materialized: table
- schema: public
- Gold Serving: PostgreSQL table (API 서빙용)
- article_enrichments 테이블과 LEFT JOIN으로 AI 결과 결합
- ref: Silver 모델 참조
- 접두사: `mart_`

### schema.yml
- 모든 레이어에 schema.yml 필수
- column tests: unique, not_null (적절한 컬럼에)
- source 정의: PostgreSQL public schema의 articles, crawl_sources, article_enrichments

## 하지 말 것
- dbt에서 raw crawling이나 HTML parsing을 하지 않는다
- dbt profiles에 DuckDB를 사용하지 않는다 (PostgreSQL 사용)
- Gold를 aggregation-only로 취급하지 않는다 (아티클 단위 서빙도 Gold)

## 검증
- `dbt run` 성공
- `dbt test` 통과
- PostgreSQL에서 Bronze view, Silver/Gold 테이블 확인
