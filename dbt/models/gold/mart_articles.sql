-- Gold layer: article mart for API serving.
-- Materialized as PostgreSQL table for Nest.js API access.

with cleaned as (
    select * from {{ ref('int_articles_cleaned') }}
)

select
    id,
    source_id,
    source_name,
    url,
    title,
    content_text,
    content_html,
    author,
    published_at,
    discovered_at,
    content_hash,
    metadata
from cleaned
where title is not null
order by published_at desc nulls last
