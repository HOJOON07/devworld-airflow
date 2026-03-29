-- Reverse ETL: export Gold keyword stats to PostgreSQL app_db for API serving.

select * from {{ ref('mart_keyword_stats') }}
