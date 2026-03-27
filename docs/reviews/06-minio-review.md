# MinIO / Object Storage 리뷰

**리뷰어**: minio-reviewer
**리뷰 일자**: 2026-03-27

---

## 리뷰 결과

### Critical (3건)

**C-1. .env 파일에 시크릿 하드코딩**
- OLLAMA_API_KEY, GITHUB_TOKEN 평문 노출

**C-2. `devworld-lake` 버킷 미생성**
- StorageConfig.lake_bucket = "devworld-lake"
- DuckLake setup.py가 참조하지만 minio-init에서 생성 안 함

**C-3. `duckdb-ui.py`에 SQL 인젝션 가능성**
- f-string으로 환경변수를 SQL에 직접 삽입

### Warning (5건)

- W-1: GitHub 파이프라인 Raw First 원칙 위반 (raw_storage_key=None)
- W-2: devworld-silver, devworld-gold-analytics 버킷 미사용
- W-3: dlt Bronze 경로와 DuckLake DATA_PATH 불일치
- W-4: datetime.utcnow() deprecated
- W-5: load_service.py partition_date 필터 미적용

### Pass (9건)

- S3Storage 클래스, StorageAdapter Protocol, Thin DAG
- Raw 저장 경로 일관성, dlt filesystem destination
- MinIO healthcheck, S3 signature_version, StorageConfig
- dbt profiles.yml (PostgreSQL 직접 타겟)

---

## 기술 문서

### MinIO 버킷 구조

| 버킷 | 상태 | 내용 |
|---|---|---|
| devworld-raw | **활성** | 블로그 raw HTML |
| devworld-bronze | **활성** | dlt Bronze parquet (미소비) |
| devworld-silver | **미사용** | 빈 버킷 (placeholder) |
| devworld-gold-analytics | **미사용** | 빈 버킷 (placeholder) |
| devworld-lake | **미생성** | config에만 존재 |

### 블로그 데이터 경로
- Raw: `raw/{source_name}/{date}/{url_hash}.html`
- Bronze: `articles/{source_name}/articles/{load_id}.parquet`

### GitHub 데이터 경로
- **없음** — GitHub은 MinIO를 사용하지 않음 (Raw First 미적용)

### R2 전환 가이드
- 환경변수만 변경: STORAGE_ENDPOINT_URL, ACCESS_KEY, SECRET_KEY
- S3Storage, dlt, DuckDB httpfs 모두 S3-compatible → R2 호환
- R2 주의: USE_SSL=true, region=auto
