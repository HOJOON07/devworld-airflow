-- Reverse ETL: export Gold source stats to PostgreSQL app_db for API serving.

select * from {{ ref('mart_source_stats') }}
