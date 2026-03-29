# 아키텍처 전체 리뷰

**리뷰어**: arch-reviewer
**리뷰 일자**: 2026-03-27
**수정 일자**: 2026-03-29 (DuckLake 전환 후)

---

## 리뷰 결과

### Critical (이전 3건) — 모두 해결됨

**1. dbt가 R2 Bronze parquet이 아닌 PostgreSQL을 source로 사용** ✅
- 이전: PostgreSQL articles → dbt → Silver/Gold (전부 PostgreSQL)
- 현재: dlt가 DuckLake Bronze 적재, dbt-duckdb가 `lake.bronze.articles` source 사용
- **판정**: 완전 해소

**2. DuckDB/DuckLake가 파이프라인에서 전혀 사용 안 됨** ✅
- 이전: setup.py 존재하나 미호출, dead infrastructure
- 현재: dlt ducklake destination, dbt-duckdb 엔진, enrich_service DuckLake 읽기, reverse_etl
- **판정**: 완전 해소

**3. Silver가 R2 parquet이 아닌 PostgreSQL 테이블** ✅
- 이전: Silver가 PostgreSQL table
- 현재: `dbt_project.yml`에서 Silver가 `+database: lake`, DuckLake parquet table
- **판정**: 완전 해소

### Warning (이전 4건 + 신규 2건)

**W-1. GitHub 파이프라인에 Raw First 원칙 미적용** 🔄
- `raw_storage_key=None` 하드코딩 유지. GitHub API raw JSON이 object storage에 미저장
- **심각도**: High

**W-2. Bronze parquet 적재가 dead code** ✅
- dbt Bronze view가 `lake.bronze.articles`를 source로 사용. 전체 파이프라인 연결됨

**W-3. Gold Analytics 레이어 미구현** 🔄
- DuckLake Gold가 parquet이므로 분석 가능하나 명시적 레이어 분리 없음
- **심각도**: Low

**W-4. 블로그 vs GitHub 파이프라인 아키텍처 불일치** 🔄
- 블로그: DuckLake 전환 완료. GitHub: PostgreSQL 직접 저장 유지 (Phase 2)
- **심각도**: Medium

**W-5. 🆕 DuckLake data_path 불일치 (devworld-bronze vs devworld-lake)**
- config.py/docker-compose: `s3://devworld-bronze`, duckdb-ui: `s3://devworld-lake`
- architecture.md는 `devworld-lake` 기준으로 문서화
- **수정 방향**: `DUCKLAKE_DATA_PATH`를 `s3://devworld-lake`로 통일

**W-6. 🆕 enrich_service.py DuckLake 연결 코드 중복**
- `enrich_service.py`의 `_connect_ducklake()`가 `ducklake/setup.py`의 `create_ducklake_connection()`과 중복
- **수정 방향**: `create_ducklake_connection(config)` import 사용

### Pass (7건)

- Thin DAG 원칙 일관 준수
- domain/application/infrastructure 레이어 분리
- Asset 기반 DAG 체이닝
- DuckLake 기반 데이터 흐름 구현 (설계 = 구현)
- reverse_etl로 서빙 분리 (app_db.serving)
- dbt_silver + dbt_gold DAG 분리
- DuckLake catalog 설정 일관성

---

## 핵심 판단

> **DuckLake 전환 성공.** 블로그 파이프라인이 CLAUDE.md 설계와 거의 완전히 일치.
> "PostgreSQL 중심 단일 DB 파이프라인" → **"DuckLake 중심 레이크하우스 + PostgreSQL serving"** 구조로 전환 완료.
> 이전 리뷰의 Option B(원칙주의)가 구현됨.

## PostgreSQL 역할 — 현재 상태

| 테이블/스키마 | 설계 레이어 | 실제 역할 | 일치 |
|---|---|---|---|
| public.articles | 운영 메타 | 크롤러 적재 (dlt source) | ✅ |
| public.crawl_sources | 운영 메타 | 소스 레지스트리 | ✅ |
| public.article_enrichments | 운영 메타 | AI enrichment 결과 | ✅ |
| public.github_* | 운영 메타 | GitHub Bronze (DuckLake 미전환) | ⚠️ Phase 2 |
| serving.mart_* | Gold Serving | reverse_etl 결과 + FTS | ✅ |
| lake (DuckLake catalog) | Lakehouse | Bronze/Silver/Gold 메타데이터 | ✅ |

---

## 기술 부채 목록 (업데이트)

| # | 항목 | 심각도 | 상태 |
|---|---|---|---|
| TD-1 | DuckDB/DuckLake 미통합 | High | ✅ 해소 |
| TD-2 | github_enrich_service.py 미존재 | High | 🔄 잔존 |
| TD-3 | GitHub raw JSON 미저장 | High | 🔄 잔존 |
| TD-4 | dlt Bronze parquet 미소비 | Medium | ✅ 해소 |
| TD-5 | Gold Analytics 미구현 | Medium | 🔄 잔존 (Low) |
| TD-6 | github_dbt_gold DAG 비활성 | Medium | 🔄 잔존 |
| TD-7 | dbt schema public_public 하드코딩 | Low | ✅ 해소 |
| TD-8 | airflow.decorators deprecated | Low | ✅ 해소 |
| TD-9 | Dedup 2단계만 (설계 4단계) | Low | 🔄 잔존 |
| TD-10 | devworld-lake 버킷 미생성 | Low | ✅ 해소 |
| TD-11 | 🆕 DuckLake data_path 불일치 | Low | 신규 |
| TD-12 | 🆕 enrich_service DuckLake 연결 중복 | Low | 신규 |

**해소 6건 / 잔존 4건 / 신규 2건**
