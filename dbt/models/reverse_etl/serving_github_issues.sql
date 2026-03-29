-- Reverse ETL: export GitHub Issues Gold to PostgreSQL serving.

select * from {{ ref('mart_github_issues') }}
