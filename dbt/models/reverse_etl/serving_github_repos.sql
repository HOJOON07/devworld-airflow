-- Reverse ETL: export GitHub repos to PostgreSQL serving for API.

select
    id,
    owner,
    name,
    full_name,
    last_collected_at,
    created_at
from {{ source('app_db', 'github_repos') }}
