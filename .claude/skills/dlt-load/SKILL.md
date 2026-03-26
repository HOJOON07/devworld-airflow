---
name: dlt-load
description: dlt pipeline으로 데이터를 Bronze parquet으로 적재
disable-model-invocation: true
argument-hint: "<source_table>"
---

$ARGUMENTS 테이블을 dlt pipeline으로 Bronze parquet에 적재하는 코드를 작성한다.

## 데이터 흐름

```
PostgreSQL (articles + crawl_sources) → dlt pipeline → MinIO Bronze bucket (parquet)
```

## 구현 규칙

### dlt pipeline 작성
- `src/application/load_service.py`에 구현
- pipeline name: `bronze_{source_name}`
- destination: `filesystem` (MinIO/R2, S3-compatible, `dlt.destinations.filesystem`)
- loader_file_format: `parquet`
- dataset_name: `articles/{source_name}`
- write_disposition: `replace` (소스 단위 덮어쓰기)
- `@dlt.resource` 데코레이터로 리소스 정의

### 환경별 설정
- Local: MinIO endpoint (STORAGE_ENDPOINT_URL)
- Prod: R2 endpoint
- credentials는 `src/shared/config.py`의 `StorageConfig`에서 가져온다

### Bronze 적재 스키마
- articles + crawl_sources JOIN한 전체 컬럼 유지
- 추가 컬럼: source_name, partition_date, crawled_at
- metadata 컬럼: `data_type: "text"` 지정 (JSONB → text 변환)

### 하지 말 것
- dlt로 HTML 크롤링이나 파싱을 하지 않는다
- dlt로 전체 파이프라인을 구성하지 않는다 (load만)
- Bronze에 변환/집계 로직을 넣지 않는다
- 운영 메타데이터(crawl_sources, crawl_jobs)를 Bronze에 넣지 않는다

## 검증
- MinIO 콘솔에서 `devworld-bronze` 버킷에 parquet 파일 확인
- DuckDB로 parquet 읽기 테스트: `SELECT * FROM read_parquet('s3://devworld-bronze/...')`
