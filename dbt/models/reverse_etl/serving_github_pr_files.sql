-- Reverse ETL: export GitHub PR files to PostgreSQL serving for API.

select
    id,
    pr_id,
    filename,
    status,
    additions,
    deletions,
    changes,
    patch
from {{ source('app_db', 'github_pr_files') }}
