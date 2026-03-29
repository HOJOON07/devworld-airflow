# MinIO / Object Storage 리뷰

**리뷰어**: minio-reviewer
**리뷰 일자**: 2026-03-27
**수정 일자**: 2026-03-29 (DuckLake 전환 후)

---

## 리뷰 결과

### Critical (이전 3건)

**C-1. .env 파일에 시크릿 하드코딩** 🔄
- `.env`는 `.gitignore`에 포함되어 Git에 노출되지 않으나, 로컬 파일에 평문 존재

**C-2. `devworld-lake` 버킷 미생성** ✅
- `docker-compose.yml` minio-init에 `mc mb --ignore-existing local/devworld-lake` 추가

**C-3. `duckdb-ui.py`에 SQL 인젝션 가능성** 🔄
- f-string SQL 여전히 존재. `enrich_service.py`, `setup.py`에도 동일 패턴 확산

### Warning (이전 5건 + 신규 1건)

**W-1: GitHub Raw First 원칙 위반** 🔄
- `raw_storage_key=None` 하드코딩 유지

**W-2: devworld-silver, devworld-gold-analytics 미사용** 🔄
- 버킷 생성되었으나 DuckLake DATA_PATH와 무관. placeholder 상태

**W-3: dlt Bronze 경로와 DuckLake DATA_PATH 불일치** ✅
- dlt가 DuckLake destination을 사용하므로 경로 관리가 DuckLake에 통합됨

**W-4: datetime.utcnow() deprecated** 🔄

**W-5: load_service.py partition_date 필터 미적용** 🔄

**W-6. 🆕 DATA_PATH가 devworld-bronze를 가리킴, devworld-lake는 미사용**
- `DUCKLAKE_DATA_PATH=s3://devworld-bronze`로 설정되어 DuckLake parquet이 bronze 버킷에 저장
- `devworld-lake` 버킷은 생성되었으나 파이프라인에서 미사용
- **수정 방향**: DATA_PATH를 `s3://devworld-lake`로 변경하거나, 불필요한 버킷 제거

### Pass (이전 9건 + 신규)

- S3Storage 클래스, StorageAdapter Protocol, Thin DAG
- Raw 저장 경로 일관성, MinIO healthcheck
- S3 signature_version, StorageConfig
- DuckLake destination으로 Bronze parquet 적재 정상 작동

---

## MinIO 버킷 구조 (업데이트)

| 버킷 | 상태 | 내용 |
|---|---|---|
| devworld-raw | **활성** | 블로그 raw HTML |
| devworld-bronze | **활성** | DuckLake parquet (Bronze+Silver+Gold, DATA_PATH 대상) |
| devworld-silver | **미사용** | 빈 버킷 (placeholder) |
| devworld-gold-analytics | **미사용** | 빈 버킷 (placeholder) |
| devworld-lake | **미사용** | 생성되었으나 DATA_PATH가 devworld-bronze를 가리킴 |

## R2 전환 가이드 (업데이트)
- 환경변수 변경: `STORAGE_ENDPOINT_URL`, `ACCESS_KEY`, `SECRET_KEY`
- `DUCKLAKE_DATA_PATH`를 R2 버킷 경로로 변경
- **주의**: `s3_use_ssl=true` 설정 필요 (현재 `false` 하드코딩 — W16 참조)
- S3Storage, dlt ducklake, dbt-duckdb httpfs 모두 S3-compatible → R2 호환
