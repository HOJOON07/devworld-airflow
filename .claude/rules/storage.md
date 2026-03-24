---
paths:
  - "**/*storage*/**"
  - "**/*repository*/**"
  - "**/*adapter*/**"
---

# 스토리지 규칙

## Raw Storage
raw object storage에는 반드시 다음이 저장되어야 한다:
- html, json, metadata, failed payload

## 환경별 API
- Local/Dev: MinIO-compatible API
- Prod: Cloudflare R2-compatible API

Storage adapter는 추상화되어야 하며,
local ↔ prod 전환이 설정 변경으로 가능해야 한다.
비즈니스 로직을 바꾸는 방식이면 안 된다.

## PostgreSQL
PostgreSQL은 운영 메타데이터 및 catalog DB다.

사용 대상:
- crawl source registry
- crawl job status
- article registry
- dedup metadata
- parser version history
- DuckLake catalog

DuckLake를 운영 메타데이터의 primary source처럼 취급하지 않는다.
