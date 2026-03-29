-- GitHub Gold: PR + AI summary + repo info joined for serving.

select
    p.id as pr_id,
    r.owner || '/' || r.name as repo_name,
    p.pr_number,
    p.title,
    p.body,
    p.state,
    p.author,
    p.labels,
    p.created_at,
    p.updated_at,
    p.merged_at,
    p.diff_text,
    p.raw_storage_key,
    s.ai_summary,
    s.key_changes,
    s.impact_analysis,
    s.change_type,
    s.ai_code_review,
    s.keywords,
    s.enriched_at
from {{ source('app_db', 'github_prs') }} p
join {{ source('app_db', 'github_repos') }} r on p.repo_id = r.id
left join {{ source('app_db', 'github_pr_ai_summaries') }} s on p.id = s.pr_id
