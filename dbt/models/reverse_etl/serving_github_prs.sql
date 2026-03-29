-- Reverse ETL: export GitHub PRs Gold to PostgreSQL serving.
-- FTS (tsvector + GIN)는 별도 Airflow task에서 생성.

select * from {{ ref('mart_github_prs') }}
