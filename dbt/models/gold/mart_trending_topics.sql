-- Gold layer: trending topics by period (daily, weekly, monthly).
-- Unnests topics JSONB array from article_enrichments.
-- API can SELECT * WHERE period = 'weekly' ORDER BY article_count DESC.

with enriched_articles as (
    select
        a.id,
        a.published_at,
        e.topics
    from {{ ref('int_articles_cleaned') }} a
    join {{ source('public', 'article_enrichments') }} e on a.id = e.article_id
    where e.topics is not null
      and a.published_at is not null
),

unnested as (
    select
        id,
        published_at,
        jsonb_array_elements_text(topics) as topic
    from enriched_articles
),

daily as (
    select
        'daily' as period,
        topic,
        count(distinct id) as article_count,
        current_date as period_start,
        current_date as period_end
    from unnested
    where published_at >= current_date - interval '1 day'
    group by topic
),

weekly as (
    select
        'weekly' as period,
        topic,
        count(distinct id) as article_count,
        current_date - interval '7 days' as period_start,
        current_date as period_end
    from unnested
    where published_at >= current_date - interval '7 days'
    group by topic
),

monthly as (
    select
        'monthly' as period,
        topic,
        count(distinct id) as article_count,
        current_date - interval '30 days' as period_start,
        current_date as period_end
    from unnested
    where published_at >= current_date - interval '30 days'
    group by topic
)

select * from daily
union all
select * from weekly
union all
select * from monthly
order by period, article_count desc
