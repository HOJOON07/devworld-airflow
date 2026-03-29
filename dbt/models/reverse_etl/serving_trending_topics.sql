-- Reverse ETL: export Gold trending topics to PostgreSQL app_db for API serving.

select * from {{ ref('mart_trending_topics') }}
