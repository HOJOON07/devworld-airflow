-- Gold layer: article mart for API serving.
-- Joins Silver articles with AI enrichments (keywords, topics, summary).

with cleaned as (
    select * from {{ ref('int_articles_cleaned') }}
),

enrichments as (
    select
        article_id,
        keywords,
        topics,
        summary as ai_summary
    from {{ source('public', 'article_enrichments') }}
)

select
    c.id,
    c.source_id,
    c.source_name,
    c.url,
    c.title,
    c.content_text,
    c.content_html,
    c.author,
    c.published_at,
    c.discovered_at,
    c.content_hash,
    c.metadata,
    e.keywords,
    e.topics,
    e.ai_summary
from cleaned c
left join enrichments e on c.id = e.article_id
where c.title is not null
order by c.published_at desc nulls last
