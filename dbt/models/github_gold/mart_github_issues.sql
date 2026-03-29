-- GitHub Gold: Issue + AI summary + repo info joined for serving.

select
    i.id as issue_id,
    r.owner || '/' || r.name as repo_name,
    i.issue_number,
    i.title,
    i.body,
    i.state,
    i.author,
    i.labels,
    i.created_at,
    i.updated_at,
    i.closed_at,
    i.linked_pr_numbers,
    i.raw_storage_key,
    s.ai_summary,
    s.key_points,
    s.suggested_solution,
    s.contribution_difficulty,
    s.keywords,
    s.enriched_at
from {{ source('app_db', 'github_issues') }} i
join {{ source('app_db', 'github_repos') }} r on i.repo_id = r.id
left join {{ source('app_db', 'github_issue_ai_summaries') }} s on i.id = s.issue_id
