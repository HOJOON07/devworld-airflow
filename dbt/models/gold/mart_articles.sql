-- Gold layer: article mart for product serving and analytics.
-- This table is materialized to PostgreSQL (Gold Serving) for API access.

with cleaned as (
    select * from {{ ref('int_articles_cleaned') }}
)

select
    id,
    source_id,
    url,
    title,
    content_text,
    author,
    published_at,
    discovered_at,
    content_hash
from cleaned
where title is not null
order by published_at desc nulls last
