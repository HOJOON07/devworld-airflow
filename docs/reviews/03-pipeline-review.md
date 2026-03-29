# 데이터 파이프라인 코드 리뷰

**리뷰어**: pipeline-reviewer
**리뷰 일자**: 2026-03-27
**수정 일자**: 2026-03-29 (DuckLake 전환 후)

---

## 리뷰 결과

### Critical (이전 4건 + 신규 1건)

**C-1. `github_enrich_service.py` 파일 미존재** 🔄
- DAG에서 import하지만 파일 없음 → 실행 시 ImportError
- **수정**: 구현 또는 DAG 비활성화

**C-2. DuckLake/R2 기반 Bronze가 아닌 MinIO filesystem 직접 적재** ✅
- `load_service.py`가 `dlt.destinations.ducklake()` 사용으로 전환 완료

**C-3. dbt Bronze/Silver가 PostgreSQL에서 실행** ✅
- dbt_project.yml에서 Bronze/Silver/Gold 모두 `lake` database (DuckLake) 대상
- reverse_etl로 PostgreSQL serving 분리

**C-4. load_service.py write_disposition="replace" + partition 미적용** 🔄
- 여전히 `write_disposition="replace"`, partition_date 필터 미사용
- DuckLake destination에서 replace는 테이블 전체 교체 → 데이터 유실 위험

**C-5. 🆕 reverse_etl post_hook PostgreSQL DDL 검증 필요**
- `serving_articles.sql` post_hook에 `tsvector`, `GIN` DDL 포함
- DuckDB postgres extension을 통한 DDL 실행 가능 여부 확인 필요

### Warning (이전 10건 + 신규 2건)

| # | 내용 | 상태 |
|---|---|---|
| W-1 | enrich_service.py 직접 SQL | 🔄 잔존 (DuckLake 읽기로 개선) |
| W-2 | load_service.py 직접 SQL | 🔄 잔존 |
| W-3 | airflow.decorators deprecated | ✅ 해결 (airflow.sdk) |
| W-4 | blog_crawl_dag sync_sources | 🔄 잔존 |
| W-5 | GitHub PR watermark max_pages | 🔄 잔존 |
| W-6 | Article `not in` 비교 | 🔄 잔존 (동작에 문제 없음) |
| W-7 | datetime.utcnow() deprecated | 🔄 잔존 (다수 파일) |
| W-8 | Dedup 2단계만 | 🔄 잔존 |
| W-9 | DuckLake setup dead code | ✅ 해결 (유틸리티로 재작성) |
| W-10 | ollama_client.py Prompt Injection | 🔄 잔존 |
| W-11 | 🆕 enrich_service DuckLake 연결 코드 중복 | 신규 |
| W-12 | 🆕 dlt_load_dag fallback에 utcnow() | 신규 |

### Pass (10건 + 신규)

- Raw First 원칙 (블로그), Thin DAG (부분), 관심사 분리
- Asset 기반 체이닝, CrawlJob 추적, ON CONFLICT upsert
- GitHub API 페이지네이션/Rate limit, 소스 관리 체계
- dbt 테스트 커버리지, 파서 팩토리 패턴
- DuckLake 기반 ELT 경로 (dlt → DuckLake → dbt → reverse_etl)
- dbt-duckdb + DuckLake attach 정상 구성

---

## 데이터 레이어 매핑 (업데이트)

| 레이어 | 설계 | 실제 | 일치 |
|---|---|---|---|
| Raw | MinIO HTML | MinIO HTML (블로그만) | ⚠️ GitHub 미적용 |
| Bronze | DuckLake parquet | DuckLake parquet (dlt) | ✅ |
| Silver | DuckLake table | DuckLake table (dbt) | ✅ |
| Gold | DuckLake table | DuckLake table (dbt) | ✅ |
| Serving | PostgreSQL | PostgreSQL (reverse_etl) | ✅ |

## 개선 우선순위 (업데이트)
1. P0: github_enrich_service 구현, reverse_etl post_hook 검증
2. P1: write_disposition → merge/append, partition_date 필터
3. P2: DuckLake 연결 코드 중복 해소, datetime.utcnow 정리
4. P3: Near-duplicate detection, Prompt injection 완화
