-- Gold layer: source (company) statistics.
-- API can SELECT * ORDER BY article_count DESC.

with articles as (
    select * from {{ ref('int_articles_cleaned') }}
),

enrichments as (
    select
        article_id,
        topics
    from {{ source('public', 'article_enrichments') }}
    where topics is not null
),

topic_counts as (
    select
        a.source_name,
        jsonb_array_elements_text(e.topics) as topic
    from articles a
    join enrichments e on a.id = e.article_id
)

select
    a.source_name,
    count(*) as article_count,
    count(distinct a.author) as author_count,
    min(a.published_at) as first_article_at,
    max(a.published_at) as last_article_at,
    (
        select topic
        from topic_counts tc
        where tc.source_name = a.source_name
        group by topic
        order by count(*) desc
        limit 1
    ) as top_topic
from articles a
group by a.source_name
order by article_count desc
