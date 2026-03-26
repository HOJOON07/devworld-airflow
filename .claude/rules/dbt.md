---
paths:
  - "**/*dbt*/**"
  - "**/*transform*/**"
  - "**/*models*/**"
---

# dbt 사용 규칙

## Profile 설정

- dbt profiles target: **PostgreSQL** (DuckDB가 아님)
- Bronze, Silver, Gold 레이어 모두 PostgreSQL에 적재한다

## Source 테이블

- `public.articles` — 크롤링된 아티클 원본
- `public.crawl_sources` — 크롤링 소스 목록
- `public.article_enrichments` — AI enrichment 결과

## 변환 흐름

- Bronze → Silver → Gold 순서로 변환
- Gold 모델에서 Silver 테이블과 `article_enrichments`를 JOIN하여 서빙 데이터 생성

## DAG 실행

- Astronomer Cosmos를 사용하여 dbt 프로젝트를 Airflow DAG (`dbt_transform`)으로 실행한다

## dbt 용도

- bronze → silver transformation
- silver → gold marts
- analytical models
- serving-oriented analytical tables
- data test

## dbt로 하면 안 되는 것

- raw crawling
- HTML parsing
- source-specific extraction

dbt는 transformation layer에 속한다. extraction layer가 아니다.
