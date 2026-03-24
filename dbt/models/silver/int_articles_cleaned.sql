-- Silver layer: cleaned and deduplicated articles.
-- Applies content hash dedup and null filtering.

with staged as (
    select * from {{ ref('stg_articles') }}
),

deduplicated as (
    select
        *,
        row_number() over (
            partition by content_hash
            order by discovered_at asc
        ) as _dedup_rank
    from staged
    where content_hash is not null
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
    raw_storage_key,
    content_hash
from deduplicated
where _dedup_rank = 1
