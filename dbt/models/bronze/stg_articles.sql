-- Bronze layer: staging view over DuckLake articles table.
-- Joins with app_db crawl_sources to add source_name.

with articles as (
    select * from {{ source('bronze_raw', 'articles') }}
),

sources as (
    select * from {{ source('app_db', 'crawl_sources') }}
)

select
    a.id,
    a.source_id,
    s.name as source_name,
    a.url,
    a.title,
    a.content_text,
    a.content_html,
    a.author,
    a.published_at,
    a.discovered_at,
    a.raw_storage_key,
    a.content_hash,
    a.metadata
from articles a
join sources s on a.source_id = s.id
