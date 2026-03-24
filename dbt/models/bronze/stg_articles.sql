-- Bronze layer: staging view over raw article data loaded by dlt.
-- Minimal transformation — type casting and column renaming only.

with source as (
    select * from {{ source('raw', 'articles') }}
)

select
    id,
    source_id,
    url,
    title,
    content_text,
    content_html,
    author,
    cast(published_at as timestamp) as published_at,
    cast(discovered_at as timestamp) as discovered_at,
    raw_storage_key,
    content_hash,
    metadata
from source
