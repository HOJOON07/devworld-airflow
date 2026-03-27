# 아키텍처 전체 리뷰

**리뷰어**: arch-reviewer
**리뷰 일자**: 2026-03-27

---

## 리뷰 결과

### Critical (3건)

**1. dbt가 R2 Bronze parquet이 아닌 PostgreSQL을 source로 사용**
- 설계: R2 raw → DuckDB 엔진 → R2 parquet → dbt → Gold
- 실제: PostgreSQL articles → dbt → Silver/Gold (전부 PostgreSQL)
- Bronze parquet은 적재만 되고 소비되지 않음

**2. DuckDB/DuckLake가 파이프라인에서 전혀 사용 안 됨**
- setup.py 존재하나 미호출, DuckLake catalog 미초기화
- dead infrastructure

**3. Silver가 R2 parquet이 아닌 PostgreSQL 테이블**
- CLAUDE.md: "Bronze/Silver 데이터를 RDS에 넣지 않는다" 위반

### Warning (4건)

- GitHub 파이프라인에 Raw First 원칙 미적용
- Bronze parquet 적재가 dead code
- Gold Analytics 레이어 미구현
- 블로그 vs GitHub 파이프라인 아키텍처 불일치

### Pass (3건)

- Thin DAG 원칙 일관 준수
- domain/application/infrastructure 레이어 분리
- Asset 기반 DAG 체이닝

---

## 핵심 판단

> 현재 프로젝트는 사실상 **"PostgreSQL 중심 단일 DB 파이프라인"**으로 동작.
> CLAUDE.md 설계(DuckLake 기반 레이크하우스)와 실제 구현이 크게 다름.

## PostgreSQL 역할 과다

| 테이블 | 설계 레이어 | 실제 역할 |
|---|---|---|
| articles | 운영 메타 | Raw + parsed 혼합 |
| stg_articles | Bronze | PG view (설계는 R2 parquet) |
| int_articles_cleaned | Silver | PG table (설계는 R2 parquet) |
| mart_* | Gold Serving | PG table (일치) |
| github_prs/issues | Bronze? | 레이어 모호 |

## 권고: Option A vs Option B

**Option A (현실주의)**: 설계를 현실에 맞춤
- CLAUDE.md에서 "Phase 1은 PG 중심" 명시
- DuckLake를 "Phase 2 미래 전환"으로 재분류
- 현재 규모에 적합, 복잡도 낮음

**Option B (원칙주의)**: 구현을 설계에 맞춤
- dbt-duckdb로 전환, R2 parquet 직접 읽기
- DuckLake 통합
- 확장성 우수, 구현 난이도 높음

**권고**: 지금은 Option A, 데이터 커지면 Option B로 마이그레이션.

---

## 기술 부채 목록 (Top 10)

| # | 항목 | 심각도 |
|---|---|---|
| TD-1 | DuckDB/DuckLake 미통합 | High |
| TD-2 | github_enrich_service.py 미존재 | High |
| TD-3 | GitHub raw JSON 미저장 | High |
| TD-4 | dlt Bronze parquet 미소비 | Medium |
| TD-5 | Gold Analytics 미구현 | Medium |
| TD-6 | github_dbt_gold DAG 비활성 | Medium |
| TD-7 | dbt schema public_public 하드코딩 | Low |
| TD-8 | airflow.decorators deprecated | Low |
| TD-9 | Dedup 2단계만 (설계 4단계) | Low |
| TD-10 | devworld-lake 버킷 미생성 | Low |
