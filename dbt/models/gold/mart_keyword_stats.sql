-- Gold layer: keyword statistics.
-- Unnests keywords JSON array from article_enrichments.
-- API can SELECT * WHERE keyword = 'react' or ORDER BY article_count DESC LIMIT 20.

with enriched_articles as (
    select
        a.id,
        a.source_name,
        a.published_at,
        e.keywords
    from {{ ref('int_articles_cleaned') }} a
    join {{ source('app_db', 'article_enrichments') }} e on a.id = e.article_id
    where e.keywords is not null
),

unnested as (
    select
        id,
        source_name,
        published_at,
        lower(trim(unnest(from_json(keywords::VARCHAR, '["VARCHAR"]')))) as keyword
    from enriched_articles
)

select
    keyword,
    count(distinct id) as article_count,
    count(distinct source_name) as source_count,
    min(published_at) as first_seen,
    max(published_at) as last_seen
from unnested
group by keyword
order by article_count desc
