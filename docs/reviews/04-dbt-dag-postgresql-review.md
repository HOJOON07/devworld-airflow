# dbt / DAG / DuckLake 리뷰

**리뷰어**: dbt-dag-reviewer
**리뷰 일자**: 2026-03-27
**수정 일자**: 2026-03-29 (DuckLake 전환 후)

---

## 변경 요약 (DuckLake 전환)

- dbt adapter: dbt-postgres → dbt-duckdb
- 저장소: PostgreSQL → DuckLake (Bronze/Silver/Gold)
- 신규 레이어: reverse_etl (DuckLake Gold → PostgreSQL app_db.serving)
- DAG 분리: dbt_transform → dbt_silver + dbt_gold
- 모든 DAG: airflow.decorators → airflow.sdk 마이그레이션 완료

---

## 리뷰 결과

### Critical (2건)

**C-1. `github_ai_enrich_dag.py` — 존재하지 않는 모듈 import** 🔄
- `src/application/github_enrich_service.py` 미존재
- 실행 시 ModuleNotFoundError

**C-2. blog_crawl_dag + blog_crawl_all_dag — Thin DAG 위반** 🔄
- 87줄, 111줄의 비즈니스 로직이 DAG에 직접 포함
- 두 DAG 간 discover → fetch → parse 흐름이 코드 중복
- **수정**: `src/application/crawl_service.py`로 공통 함수 추출

### Warning (8건)

| # | 내용 | 상태 |
|---|---|---|
| W-1 | datetime.utcnow() deprecated (blog_crawl_all_dag) | 🔄 |
| W-2 | 🆕 reverse_etl에서 `{{ ref() }}` 대신 hardcoded 참조 → lineage 단절 | 신규 |
| W-3 | CLAUDE.md DAG 이름 불일치 (`dbt_transform` vs `dbt_silver`+`dbt_gold`) | 🔄 |
| W-4 | mart_source_stats 상관 서브쿼리 | 🔄 |
| W-5 | 🆕 mart_articles.sql `now() as created_at` 비결정성 | 신규 |
| W-6 | DAG retry/timeout 미설정 | 🔄 |
| W-7 | DAG on_failure_callback 미구성 | 🔄 |
| W-8 | dbt source freshness 미설정 | 🔄 |

### Resolved (이전 리뷰 대비)

- ~~airflow.decorators deprecated~~ → airflow.sdk 마이그레이션 완료 ✅
- ~~dbt_project.yml 스키마 불일치~~ → lake.bronze/silver/gold + app_db.serving 정상 ✅
- ~~profiles.yml 환경 분리~~ → env_var 기반 ✅

### Pass

- Asset 기반 트리거 체인 완성
- Dynamic Task Mapping (blog_crawl_all, dlt_load)
- Cosmos로 dbt 실행 (DuckDB profile)
- dbt_silver + dbt_gold DAG 분리
- reverse_etl이 dbt_gold DAG 내에서 실행 (gold_transform >> reverse_etl >> mark_gold_ready)

---

## dbt 모델 의존성 (DuckLake 기준)

```
[DuckLake Bronze]
source(bronze_raw.articles) + source(app_db.crawl_sources)
       ↓
stg_articles (view, lake.bronze)
       ↓
int_articles_cleaned (table, lake.silver)
       ↓                               ↗ source(app_db.article_enrichments)
       ├── mart_articles ──────────────┘
       ├── mart_trending_topics ───────┘
       ├── mart_keyword_stats  ────────┘
       └── mart_source_stats   ────────┘
              (tables, lake.gold)
                     ↓
       [reverse_etl → app_db.serving]
       ├── serving_articles (+ tsvector + GIN)
       ├── serving_trending_topics
       ├── serving_keyword_stats
       └── serving_source_stats
```

**주의**: reverse_etl 모델이 `{{ ref() }}` 대신 `lake.gold.*` 직접 참조 → lineage 단절
