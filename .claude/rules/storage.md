---
paths:
  - "**/*storage*/**"
  - "**/*repository*/**"
  - "**/*adapter*/**"
---

# 스토리지 규칙

## 레이어별 저장소 매핑

| 레이어 | 저장소 | 포맷 | 비고 |
|---|---|---|---|
| Raw | MinIO `devworld-raw` | HTML | 원본 보존 |
| Bronze | MinIO `devworld-bronze` | parquet | dlt가 적재 |
| Silver | PostgreSQL | 테이블 | dbt가 적재 (MinIO 아님) |
| Gold | PostgreSQL | 테이블 | dbt가 적재 (MinIO 아님) |

## Raw Storage
raw object storage에는 반드시 다음이 저장되어야 한다:
- html, json, metadata, failed payload

## 환경별 API
- Local/Dev: MinIO-compatible API
- Prod: Cloudflare R2-compatible API

Storage adapter는 추상화되어야 하며,
local ↔ prod 전환이 설정 변경으로 가능해야 한다.
비즈니스 로직을 바꾸는 방식이면 안 된다.

## DuckDB / DuckLake
- DuckDB는 분석용 쿼리 엔진이다 (Bronze parquet 조회 등)
- 상주 서버가 아닌 ETL 컨테이너 내부에서 실행
- DuckLake를 운영 메타데이터의 primary source처럼 취급하지 않는다

## PostgreSQL
PostgreSQL은 운영 메타데이터, Silver/Gold 서빙, catalog DB다.

사용 대상:
- crawl source registry
- crawl job status
- article registry (`articles`)
- article_enrichments (AI enrichment 결과)
- dedup metadata
- parser version history
- DuckLake catalog
- Silver/Gold 변환 결과 (dbt)
