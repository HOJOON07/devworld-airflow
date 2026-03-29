-- Reverse ETL: export Gold mart_articles to PostgreSQL app_db for API serving.
-- FTS (tsvector + GIN)는 별도 Airflow task에서 PostgreSQL에 직접 생성.
-- dbt-duckdb는 모든 SQL을 DuckDB로 실행하므로 PostgreSQL 전용 DDL(tsvector, GIN)을 post_hook에 넣을 수 없음.

select
    article_id,
    source_id,
    source_name,
    url,
    title,
    content_text,
    author,
    published_at,
    discovered_at,
    content_hash,
    keywords,
    topics,
    ai_summary,
    keyword_count,
    has_summary,
    created_at
from {{ ref('mart_articles') }}
