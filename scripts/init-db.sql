-- Create devworld role for app_db access
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'devworld') THEN
        CREATE ROLE devworld WITH LOGIN PASSWORD 'devworld';
    END IF;
END
$$;

-- Create app_db for Gold Serving data (Nest.js API reads from this)
SELECT 'CREATE DATABASE app_db OWNER devworld'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'app_db')\gexec

-- Switch to app_db and create tables
\c app_db

-- Grant schema usage to devworld
GRANT ALL PRIVILEGES ON SCHEMA public TO devworld;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO devworld;

-- Serving schema for reverse_etl (dbt creates tables here)
CREATE SCHEMA IF NOT EXISTS serving;
GRANT ALL PRIVILEGES ON SCHEMA serving TO devworld;
ALTER DEFAULT PRIVILEGES IN SCHEMA serving GRANT ALL ON TABLES TO devworld;

-- ============================================================
-- crawl_sources: 크롤링 대상 소스 레지스트리
-- ============================================================
CREATE TABLE IF NOT EXISTS crawl_sources (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    base_url VARCHAR(1024) NOT NULL,
    feed_url VARCHAR(1024),
    crawl_config JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- articles: 크롤링된 아티클
-- ============================================================
CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES crawl_sources(id),
    url VARCHAR(2048) NOT NULL UNIQUE,
    title VARCHAR(1024),
    content_text TEXT,
    content_html TEXT,
    author VARCHAR(255),
    published_at TIMESTAMP,
    discovered_at TIMESTAMP NOT NULL,
    raw_storage_key VARCHAR(1024),
    content_hash VARCHAR(64),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- crawl_jobs: 크롤링 작업 이력
-- ============================================================
CREATE TABLE IF NOT EXISTS crawl_jobs (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES crawl_sources(id),
    partition_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    discovered_count INTEGER DEFAULT 0,
    fetched_count INTEGER DEFAULT 0,
    parsed_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- ============================================================
-- article_enrichments: AI enrichment 결과 (keywords, topics)
-- ============================================================
CREATE TABLE IF NOT EXISTS article_enrichments (
    article_id UUID PRIMARY KEY REFERENCES articles(id),
    keywords JSONB,
    topics JSONB,
    summary TEXT,
    enriched_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_source_id ON crawl_jobs(source_id);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_partition ON crawl_jobs(source_id, partition_date);

-- ============================================================
-- Seed: 초기 크롤링 소스 (한국 기술 블로그 RSS)
-- ============================================================
INSERT INTO crawl_sources (id, name, source_type, base_url, feed_url, is_active) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'naver-d2', 'rss',
     'https://d2.naver.com', 'https://d2.naver.com/d2/rss', true),
    ('a1000000-0000-0000-0000-000000000002', 'kakao-tech', 'rss',
     'https://tech.kakao.com', 'https://tech.kakao.com/feed', true),
    ('a1000000-0000-0000-0000-000000000003', 'woowahan-tech', 'rss',
     'https://techblog.woowahan.com', 'https://techblog.woowahan.com/feed', true),
    ('a1000000-0000-0000-0000-000000000004', 'toss-tech', 'rss',
     'https://toss.tech', 'https://toss.tech/rss.xml', true),
    ('a1000000-0000-0000-0000-000000000005', 'line-engineering', 'rss',
     'https://engineering.linecorp.com', 'https://engineering.linecorp.com/ko/blog/rss', true),
    ('a1000000-0000-0000-0000-000000000006', 'daangn-tech', 'rss',
     'https://medium.com/daangn', 'https://medium.com/feed/daangn', true)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- GitHub 레포 레지스트리
-- ============================================================
CREATE TABLE IF NOT EXISTS github_repos (
    id UUID PRIMARY KEY,
    owner VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(511) NOT NULL UNIQUE,
    last_collected_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- GitHub PR
-- ============================================================
CREATE TABLE IF NOT EXISTS github_prs (
    id UUID PRIMARY KEY,
    repo_id UUID NOT NULL REFERENCES github_repos(id),
    pr_number INTEGER NOT NULL,
    title VARCHAR(1024),
    body TEXT,
    state VARCHAR(20),
    author VARCHAR(255),
    labels JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    merged_at TIMESTAMP,
    diff_text TEXT,
    raw_storage_key VARCHAR(1024),
    metadata JSONB,
    UNIQUE(repo_id, pr_number)
);

-- ============================================================
-- GitHub PR 파일
-- ============================================================
CREATE TABLE IF NOT EXISTS github_pr_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pr_id UUID NOT NULL REFERENCES github_prs(id),
    filename VARCHAR(1024),
    status VARCHAR(20),
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    changes INTEGER DEFAULT 0,
    patch TEXT
);

-- ============================================================
-- GitHub Issue
-- ============================================================
CREATE TABLE IF NOT EXISTS github_issues (
    id UUID PRIMARY KEY,
    repo_id UUID NOT NULL REFERENCES github_repos(id),
    issue_number INTEGER NOT NULL,
    title VARCHAR(1024),
    body TEXT,
    state VARCHAR(20),
    author VARCHAR(255),
    labels JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    closed_at TIMESTAMP,
    linked_pr_numbers JSONB,
    raw_storage_key VARCHAR(1024),
    metadata JSONB,
    UNIQUE(repo_id, issue_number)
);

-- ============================================================
-- GitHub PR AI 요약
-- ============================================================
CREATE TABLE IF NOT EXISTS github_pr_ai_summaries (
    pr_id UUID PRIMARY KEY REFERENCES github_prs(id),
    ai_summary TEXT,
    key_changes JSONB,
    impact_analysis TEXT,
    change_type VARCHAR(20),
    ai_code_review TEXT,
    keywords JSONB,
    enriched_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- GitHub Issue AI 요약
-- ============================================================
CREATE TABLE IF NOT EXISTS github_issue_ai_summaries (
    issue_id UUID PRIMARY KEY REFERENCES github_issues(id),
    ai_summary TEXT,
    key_points JSONB,
    suggested_solution TEXT,
    contribution_difficulty VARCHAR(20),
    keywords JSONB,
    enriched_at TIMESTAMP DEFAULT NOW()
);

-- GitHub Indexes
CREATE INDEX IF NOT EXISTS idx_github_prs_repo ON github_prs(repo_id);
CREATE INDEX IF NOT EXISTS idx_github_prs_state ON github_prs(state);
CREATE INDEX IF NOT EXISTS idx_github_issues_repo ON github_issues(repo_id);
CREATE INDEX IF NOT EXISTS idx_github_issues_state ON github_issues(state);
CREATE INDEX IF NOT EXISTS idx_github_pr_files_pr ON github_pr_files(pr_id);