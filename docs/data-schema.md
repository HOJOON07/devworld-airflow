# 데이터 스키마 문서

**작성일**: 2026-03-30

---

## 전체 데이터 흐름

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  [Raw]           [Operational]        [Bronze]      [Silver]     [Gold]      │
│  MinIO/R2        PostgreSQL           DuckLake      DuckLake     DuckLake    │
│  HTML/JSON       app_db.public        devworld_lake devworld_lake devworld_lake │
│                                                                             │
│  블로그 파이프라인:                                                           │
│  raw/*.html  →   articles         →   bronze.      → silver.    → gold.      │
│                  crawl_sources        articles       int_articles  mart_*     │
│                  crawl_jobs           (dlt)          _cleaned      (dbt)      │
│                  article_enrichments                 (dbt)                    │
│                                                                             │
│  GitHub 파이프라인:                                                           │
│  raw/*.json  →   github_prs      ─────────────────────────────→ github_gold. │
│                  github_issues                                   mart_*      │
│                  github_pr_files                                 (dbt)       │
│                  github_*_ai_summaries                                       │
│                                                                             │
│                                                          [Serving]           │
│                                                          PostgreSQL          │
│                                                          app_db.serving      │
│                                                          serving_*           │
│                                                          (reverse_etl)       │
│                                                              ↓               │
│                                                          Nest.js API         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 테이블 관계도

### 블로그 파이프라인

```
crawl_sources (소스 레지스트리)
    │
    ├──── articles (크롤링 결과)
    │         │
    │         └──── article_enrichments (AI 결과)
    │
    └──── crawl_jobs (크롤링 추적)

articles ──[dlt]──→ bronze.articles ──[dbt]──→ silver.int_articles_cleaned
                                                       │
                     article_enrichments ───────────────┘ (LEFT JOIN)
                                                       │
                                                       ▼
                                              gold.mart_articles
                                              gold.mart_trending_topics
                                              gold.mart_keyword_stats
                                              gold.mart_source_stats
                                                       │
                                                [reverse_etl]
                                                       ▼
                                              serving.serving_articles (+ FTS)
                                              serving.serving_trending_topics
                                              serving.serving_keyword_stats
                                              serving.serving_source_stats
```

### GitHub 파이프라인

```
github_repos (레포 레지스트리)
    │
    ├──── github_prs
    │         │
    │         ├──── github_pr_files (파일별 diff)
    │         │
    │         └──── github_pr_ai_summaries (AI 요약)
    │
    └──── github_issues
              │
              └──── github_issue_ai_summaries (AI 요약)

github_prs + github_repos + github_pr_ai_summaries
    ──[dbt JOIN]──→ github_gold.mart_github_prs
                           │
                    [reverse_etl]
                           ▼
                    serving.serving_github_prs (+ FTS)

github_issues + github_repos + github_issue_ai_summaries
    ──[dbt JOIN]──→ github_gold.mart_github_issues
                           │
                    [reverse_etl]
                           ▼
                    serving.serving_github_issues
```

---

## 레이어별 테이블 상세

### 1. Operational Layer (PostgreSQL app_db.public)

크롤러와 수집기가 직접 적재하는 원본 데이터.

#### crawl_sources — 크롤링 소스 레지스트리

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(255) | 소스 이름 (toss-tech, naver-d2 등) |
| source_type | VARCHAR(50) | rss, web 등 |
| base_url | VARCHAR(1024) | 블로그 URL |
| feed_url | VARCHAR(1024) | RSS feed URL |
| crawl_config | JSONB | url_filter 등 크롤링 설정 |
| is_active | BOOLEAN | 활성 여부 |
| created_at | TIMESTAMP | 생성일 |

#### articles — 크롤링된 블로그 아티클

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | UUID | PK |
| source_id | UUID | FK → crawl_sources.id |
| url | VARCHAR(2048) | UNIQUE, 아티클 URL |
| title | VARCHAR(1024) | 제목 |
| content_text | TEXT | 본문 텍스트 |
| content_html | TEXT | 본문 HTML |
| author | VARCHAR(255) | 작성자 |
| published_at | TIMESTAMP | 발행일 |
| discovered_at | TIMESTAMP | 수집일 |
| raw_storage_key | VARCHAR(1024) | MinIO Raw HTML 경로 |
| content_hash | VARCHAR(64) | SHA-256 해시 (dedup용) |
| metadata | JSONB | 추가 메타데이터 |
| created_at | TIMESTAMP | 생성일 |

**인덱스**: `idx_articles_source_id`, `idx_articles_url`, `idx_articles_content_hash`

#### crawl_jobs — 크롤링 작업 추적

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | UUID | PK |
| source_id | UUID | FK → crawl_sources.id |
| partition_date | DATE | 파티션 날짜 |
| status | VARCHAR(20) | pending/running/success/failed |
| discovered_count | INTEGER | 발견 수 |
| fetched_count | INTEGER | 수집 수 |
| parsed_count | INTEGER | 파싱 수 |
| error_message | TEXT | 에러 메시지 |
| started_at | TIMESTAMP | 시작 시간 |
| completed_at | TIMESTAMP | 완료 시간 |

#### article_enrichments — AI 추출 결과

| 컬럼 | 타입 | 설명 |
|---|---|---|
| article_id | UUID | PK, FK → articles.id |
| keywords | JSONB | 기술 키워드 리스트 |
| topics | JSONB | 토픽/카테고리 리스트 |
| summary | TEXT | AI 생성 요약 |
| enriched_at | TIMESTAMP | 처리 시간 |

#### github_repos — GitHub 추적 레포

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | UUID | PK |
| owner | VARCHAR(255) | 레포 소유자 (facebook, vercel 등) |
| name | VARCHAR(255) | 레포 이름 (react, next.js 등) |
| full_name | VARCHAR(511) | UNIQUE, owner/name |
| last_collected_at | TIMESTAMP | 마지막 수집 시간 (watermark) |
| created_at | TIMESTAMP | 생성일 |

#### github_prs — GitHub Pull Requests

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | UUID | PK |
| repo_id | UUID | FK → github_repos.id |
| pr_number | INTEGER | PR 번호 |
| title | VARCHAR(1024) | PR 제목 |
| body | TEXT | PR 설명 |
| state | VARCHAR(20) | open/closed/merged |
| author | VARCHAR(255) | 작성자 |
| labels | JSONB | 라벨 리스트 |
| created_at | TIMESTAMP | 생성일 |
| updated_at | TIMESTAMP | 수정일 |
| merged_at | TIMESTAMP | 머지일 |
| diff_text | TEXT | 상위 10개 파일 patch 합침 |
| raw_storage_key | VARCHAR(1024) | MinIO Raw JSON 경로 |
| metadata | JSONB | html_url, base_ref, head_ref |

**제약**: UNIQUE(repo_id, pr_number)
**인덱스**: `idx_github_prs_repo`, `idx_github_prs_state`

#### github_pr_files — PR 파일별 변경사항

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | UUID | PK (자동 생성) |
| pr_id | UUID | FK → github_prs.id |
| filename | VARCHAR(1024) | 변경 파일 경로 |
| status | VARCHAR(20) | added/modified/removed/renamed |
| additions | INTEGER | 추가 줄 수 |
| deletions | INTEGER | 삭제 줄 수 |
| changes | INTEGER | 총 변경 줄 수 |
| patch | TEXT | 파일별 diff (상위 10개만) |

#### github_issues — GitHub Issues

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | UUID | PK |
| repo_id | UUID | FK → github_repos.id |
| issue_number | INTEGER | Issue 번호 |
| title | VARCHAR(1024) | Issue 제목 |
| body | TEXT | Issue 설명 |
| state | VARCHAR(20) | open/closed |
| author | VARCHAR(255) | 작성자 |
| labels | JSONB | 라벨 리스트 |
| created_at | TIMESTAMP | 생성일 |
| updated_at | TIMESTAMP | 수정일 |
| closed_at | TIMESTAMP | 종료일 |
| linked_pr_numbers | JSONB | 연결된 PR 번호 (body에서 파싱) |
| raw_storage_key | VARCHAR(1024) | MinIO Raw JSON 경로 |
| metadata | JSONB | html_url, comments |

**제약**: UNIQUE(repo_id, issue_number)

#### github_pr_ai_summaries — PR AI 요약

| 컬럼 | 타입 | 설명 |
|---|---|---|
| pr_id | UUID | PK, FK → github_prs.id |
| ai_summary | TEXT | PR 요약 |
| key_changes | JSONB | 핵심 변경사항 리스트 |
| impact_analysis | TEXT | 영향 분석 |
| change_type | VARCHAR(20) | feature/bugfix/refactor/docs/test/chore |
| ai_code_review | TEXT | 코드 리뷰 포인트 |
| keywords | JSONB | 기술 키워드 |
| enriched_at | TIMESTAMP | 처리 시간 |

#### github_issue_ai_summaries — Issue AI 요약

| 컬럼 | 타입 | 설명 |
|---|---|---|
| issue_id | UUID | PK, FK → github_issues.id |
| ai_summary | TEXT | Issue 요약 |
| key_points | JSONB | 핵심 포인트 리스트 |
| suggested_solution | TEXT | 해결 제안 |
| contribution_difficulty | VARCHAR(20) | beginner/intermediate/advanced |
| keywords | JSONB | 기술 키워드 |
| enriched_at | TIMESTAMP | 처리 시간 |

---

### 2. Bronze Layer (DuckLake devworld_lake.bronze)

dlt가 PostgreSQL articles를 DuckLake parquet으로 적재.

#### bronze.articles — dlt 적재 테이블 (Parquet)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | TEXT | articles.id |
| source_id | TEXT | articles.source_id |
| source_name | TEXT | crawl_sources.name (JOIN) |
| url | TEXT | 아티클 URL |
| title | TEXT | 제목 |
| content_text | TEXT | 본문 텍스트 |
| content_html | TEXT | 본문 HTML |
| author | TEXT | 작성자 |
| published_at | TEXT | 발행일 (text로 저장) |
| discovered_at | TEXT | 수집일 |
| raw_storage_key | TEXT | MinIO 경로 |
| content_hash | TEXT | SHA-256 해시 |
| metadata | TEXT | 메타데이터 (text로 저장) |
| partition_date | TEXT | 파티션 날짜 |
| crawled_at | TEXT | 적재 시간 |

**적재 도구**: dlt ducklake destination
**적재 방식**: append, partition_date 필터

#### bronze.stg_articles — dbt Bronze View

`bronze.articles`와 `app_db.crawl_sources`를 JOIN한 스테이징 뷰.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | UUID | 아티클 ID |
| source_id | UUID | 소스 ID |
| source_name | VARCHAR | crawl_sources.name |
| url | VARCHAR | 아티클 URL |
| title | VARCHAR | 제목 |
| content_text | TEXT | 본문 텍스트 |
| content_html | TEXT | 본문 HTML |
| author | VARCHAR | 작성자 |
| published_at | TIMESTAMP | 발행일 |
| discovered_at | TIMESTAMP | 수집일 |
| raw_storage_key | VARCHAR | MinIO 경로 |
| content_hash | VARCHAR | SHA-256 해시 |
| metadata | JSONB | 메타데이터 |

**Materialization**: VIEW

---

### 3. Silver Layer (DuckLake devworld_lake.silver)

정규화/정제/중복 제거.

#### silver.int_articles_cleaned — 정제된 아티클

`stg_articles`에서 `content_hash` 기준으로 중복 제거 (ROW_NUMBER PARTITION BY content_hash ORDER BY discovered_at).

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | UUID | PK (unique 테스트) |
| source_id | UUID | 소스 ID |
| source_name | VARCHAR | 소스 이름 |
| url | VARCHAR | 아티클 URL (not_null 테스트) |
| title | VARCHAR | 제목 |
| content_text | TEXT | 본문 텍스트 |
| content_html | TEXT | 본문 HTML |
| author | VARCHAR | 작성자 |
| published_at | TIMESTAMP | 발행일 |
| discovered_at | TIMESTAMP | 수집일 |
| raw_storage_key | VARCHAR | MinIO 경로 |
| content_hash | VARCHAR | SHA-256 해시 (unique 테스트) |
| metadata | JSONB | 메타데이터 |

**Materialization**: TABLE
**Dedup**: content_hash 기준 중복 제거

---

### 4. Gold Layer (DuckLake devworld_lake.gold)

서빙/분석용 집계 데이터.

#### gold.mart_articles — 아티클 서빙 마트

Silver + AI enrichments LEFT JOIN.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| article_id | UUID | PK (unique 테스트) |
| source_id | UUID | 소스 ID |
| source_name | VARCHAR | 소스 이름 |
| url | VARCHAR | 아티클 URL |
| title | VARCHAR | 제목 |
| content_text | TEXT | 본문 |
| author | VARCHAR | 작성자 |
| published_at | TIMESTAMP | 발행일 |
| discovered_at | TIMESTAMP | 수집일 |
| content_hash | VARCHAR | 해시 |
| keywords | JSONB | AI 키워드 |
| topics | JSONB | AI 토픽 |
| ai_summary | TEXT | AI 요약 |
| keyword_count | INTEGER | 키워드 수 |
| has_summary | BOOLEAN | 요약 존재 여부 |
| created_at | TIMESTAMP | 마트 생성 시간 |

#### gold.mart_trending_topics — 트렌딩 토픽

| 컬럼 | 타입 | 설명 |
|---|---|---|
| period | VARCHAR | daily/weekly/monthly |
| topic | VARCHAR | 토픽명 |
| article_count | INTEGER | 아티클 수 |
| period_start | DATE | 기간 시작일 |
| period_end | DATE | 기간 종료일 |

#### gold.mart_keyword_stats — 키워드 통계

| 컬럼 | 타입 | 설명 |
|---|---|---|
| keyword | VARCHAR | 키워드 (소문자 정규화) |
| article_count | INTEGER | 언급 아티클 수 |
| source_count | INTEGER | 언급 소스 수 |
| first_seen | TIMESTAMP | 최초 등장일 |
| last_seen | TIMESTAMP | 최근 등장일 |

#### gold.mart_source_stats — 소스별 통계

| 컬럼 | 타입 | 설명 |
|---|---|---|
| source_name | VARCHAR | 소스 이름 |
| article_count | INTEGER | 아티클 수 |
| author_count | INTEGER | 작성자 수 |
| first_article_at | TIMESTAMP | 첫 아티클 |
| last_article_at | TIMESTAMP | 최근 아티클 |
| top_topic | VARCHAR | 최다 토픽 |

---

### 5. GitHub Gold Layer (DuckLake devworld_lake.github_gold)

#### github_gold.mart_github_prs — PR 서빙 마트

github_prs + github_repos + github_pr_ai_summaries JOIN.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| pr_id | UUID | PK |
| repo_name | VARCHAR | owner/name (facebook/react 등) |
| pr_number | INTEGER | PR 번호 |
| title | VARCHAR | PR 제목 |
| body | TEXT | PR 설명 |
| state | VARCHAR | open/closed/merged |
| author | VARCHAR | 작성자 |
| labels | JSONB | 라벨 |
| created_at | TIMESTAMP | 생성일 |
| updated_at | TIMESTAMP | 수정일 |
| merged_at | TIMESTAMP | 머지일 |
| diff_text | TEXT | 코드 diff (상위 10파일) |
| raw_storage_key | VARCHAR | MinIO Raw JSON 경로 |
| ai_summary | TEXT | AI PR 요약 |
| key_changes | JSONB | AI 핵심 변경사항 |
| impact_analysis | TEXT | AI 영향 분석 |
| change_type | VARCHAR | feature/bugfix/refactor/... |
| ai_code_review | TEXT | AI 코드 리뷰 |
| keywords | JSONB | AI 키워드 |
| enriched_at | TIMESTAMP | AI 처리 시간 |

#### github_gold.mart_github_issues — Issue 서빙 마트

github_issues + github_repos + github_issue_ai_summaries JOIN.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| issue_id | UUID | PK |
| repo_name | VARCHAR | owner/name |
| issue_number | INTEGER | Issue 번호 |
| title | VARCHAR | Issue 제목 |
| body | TEXT | Issue 설명 |
| state | VARCHAR | open/closed |
| author | VARCHAR | 작성자 |
| labels | JSONB | 라벨 |
| created_at | TIMESTAMP | 생성일 |
| updated_at | TIMESTAMP | 수정일 |
| closed_at | TIMESTAMP | 종료일 |
| linked_pr_numbers | JSONB | 연결된 PR 번호 |
| raw_storage_key | VARCHAR | MinIO Raw JSON 경로 |
| ai_summary | TEXT | AI Issue 요약 |
| key_points | JSONB | AI 핵심 포인트 |
| suggested_solution | TEXT | AI 해결 제안 |
| contribution_difficulty | VARCHAR | beginner/intermediate/advanced |
| keywords | JSONB | AI 키워드 |
| enriched_at | TIMESTAMP | AI 처리 시간 |

---

### 6. Serving Layer (PostgreSQL app_db.serving)

dbt reverse_etl이 DuckLake Gold → PostgreSQL로 복사. Nest.js API가 조회.

| 테이블 | 원본 | FTS | 설명 |
|---|---|---|---|
| serving_articles | gold.mart_articles | tsvector + GIN | 블로그 아티클 서빙 |
| serving_trending_topics | gold.mart_trending_topics | - | 트렌딩 토픽 |
| serving_keyword_stats | gold.mart_keyword_stats | - | 키워드 통계 |
| serving_source_stats | gold.mart_source_stats | - | 소스 통계 |
| serving_github_prs | github_gold.mart_github_prs | tsvector + GIN | GitHub PR 서빙 |
| serving_github_issues | github_gold.mart_github_issues | - | GitHub Issue 서빙 |

컬럼은 각 Gold 원본과 동일. `serving_articles`와 `serving_github_prs`에는 별도 Airflow task에서 `search_vector` (tsvector) 컬럼과 GIN 인덱스가 추가됨.

---

## 테이블 수 요약

| 레이어 | 저장소 | 테이블 수 |
|---|---|---|
| Operational | PostgreSQL app_db.public | 10 |
| Bronze | DuckLake devworld_lake.bronze | 2 (articles + stg_articles view) |
| Silver | DuckLake devworld_lake.silver | 1 |
| Gold | DuckLake devworld_lake.gold | 4 |
| GitHub Gold | DuckLake devworld_lake.github_gold | 2 |
| Serving | PostgreSQL app_db.serving | 6 |
| **합계** | | **25** |
