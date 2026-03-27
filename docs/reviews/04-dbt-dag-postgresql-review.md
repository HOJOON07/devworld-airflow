# dbt / DAG / PostgreSQL 리뷰

**리뷰어**: dbt-dag-pg-reviewer
**리뷰 일자**: 2026-03-27

---

## 리뷰 결과

### Critical (3건)

**C-1. `github_ai_enrich_dag.py` — 존재하지 않는 모듈 import**
- `github_enrich_service.py` 미존재 → ModuleNotFoundError

**C-2. `blog_crawl_dag.py` — Thin DAG 위반**
- crawl 태스크에 80줄+ 비즈니스 로직 직접 포함
- blog_crawl_all_dag.py와 코드 중복
- 수정: 공통 서비스 함수로 추출

**C-3. 모든 DAG에서 `airflow.decorators` 사용 (deprecated)**
- `.claude/rules/dags.md`에서 `airflow.sdk` 권장하나 미적용
- `assets.py`만 `airflow.sdk` 사용 → 혼재 상태

### Warning (7건)

- W-1: datetime.utcnow() deprecated
- W-2: dbt_project.yml Bronze/Silver/Gold 스키마 설정 불일치
- W-3: dbt_silver_dag에 bronze + silver 모두 select 포함
- W-4: mart_source_stats.sql 상관 서브쿼리 성능
- W-5: profiles.yml dev와 prod 설정 동일
- W-6: init-db.sql 시드 데이터 + sources.yml 이중 관리
- W-7: GitHub 테이블에 published_at 없음 (블로그와 정렬 기준 불일치)

### Pass (7건)

- Asset 기반 트리거 체인 (블로그 + GitHub)
- dbt 모델 의존성 체인 올바름
- PostgreSQL FK/인덱스 구조 적절
- Gold 마트 FTS + GIN 인덱스 적합
- Astronomer Cosmos 사용 패턴
- Dynamic Task Mapping

---

## 기술 문서

### DAG 구성도

**블로그**: blog_crawl_all → dlt_load → dbt_silver → ai_enrich → dbt_gold
**GitHub**: github_collect → github_ai_enrich (미구현) → github_dbt_gold (비활성)
**수동**: blog_crawl (Asset outlet 없음)

### dbt 모델 의존성

```
source(articles, crawl_sources) → stg_articles(view) → int_articles_cleaned(table)
source(article_enrichments) ──────────────────────────────┐
                                                           ↓
mart_articles, mart_trending_topics, mart_keyword_stats, mart_source_stats
```

### PostgreSQL 스키마
- 블로그: crawl_sources, articles, crawl_jobs, article_enrichments (4 테이블)
- GitHub: github_repos, github_prs, github_pr_files, github_issues, github_pr/issue_ai_summaries (6 테이블)
- dbt: stg_articles(view), int_articles_cleaned, mart_*(4 tables) — schema: public_public

### dbt가 parquet을 못 읽는 한계
- dbt-postgres는 MinIO parquet 접근 불가
- 실제: dbt가 PostgreSQL articles를 직접 source로 사용
- dlt Bronze parquet은 소비자 없는 dead data
