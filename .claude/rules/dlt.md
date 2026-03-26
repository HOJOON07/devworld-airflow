---
paths:
  - "**/*dlt*/**"
  - "**/*load*/**"
---

# dlt 사용 규칙

## Destination 설정

- destination: `filesystem` (S3-compatible — MinIO/R2)
- `loader_file_format`: `parquet`
- pipeline_name: source별로 분리한다 (예: `bronze_{source_name}`)

## 데이터 흐름

- PostgreSQL `articles` 테이블에서 읽어 MinIO Bronze 버킷에 parquet로 적재한다
- metadata 컬럼은 SQL에서 `::text` 캐스팅하여 추출한다

## dlt 용도

- structured loading
- incremental structured ingestion
- normalized record loading

## dlt로 대체하면 안 되는 것

- HTML crawling
- source-specific parsing
- 전체 orchestration
- dedup 설계

dlt는 load layer의 일부이지, 전체 파이프라인 자체가 아니다.
