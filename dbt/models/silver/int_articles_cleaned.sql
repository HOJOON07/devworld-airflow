-- Silver layer: cleaned and deduplicated articles.
-- Applies content hash dedup and null filtering.

with staged as (
    select * from {{ ref('stg_articles') }}
    where content_hash is not null
),

deduplicated as (
    select
        *,
        row_number() over (
            partition by content_hash
            order by discovered_at asc
        ) as _dedup_rank
    from staged
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
    raw_storage_key,
    content_hash,
    metadata
from deduplicated
where _dedup_rank = 1
