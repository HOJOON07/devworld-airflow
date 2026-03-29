-- Gold layer: article mart for analytics/serving.
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
    from {{ source('app_db', 'article_enrichments') }}
)

select
    c.id as article_id,
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
    e.ai_summary,
    coalesce(json_array_length(e.keywords::JSON), 0) as keyword_count,
    e.ai_summary is not null as has_summary,
    now() as created_at

from cleaned c
left join enrichments e on c.id = e.article_id
where c.title is not null
order by c.published_at desc nulls last
