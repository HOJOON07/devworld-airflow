# devworld-airflow 아키텍처 문서

**작성일**: 2026-03-29

---

## 1. 전체 플랫폼 구조

```
devworld (플랫폼)
├── Frontend     — Next.js → Vercel
├── Backend API  — Nest.js → ECS Fargate + ALB
└── Data Pipeline — Python + Airflow → ECS Fargate  ← 이 레포
```

이 레포(`devworld-airflow`)는 데이터 ETL 파이프라인만 담당한다.
Nest.js API는 PostgreSQL `app_db.serving` 스키마만 조회한다.

---

## 2. 데이터 파이프라인 아키텍처

### 전체 데이터 흐름

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          Data Sources                                    │
│                                                                          │
│   ┌─────────────┐          ┌──────────────┐          ┌───────────────┐  │
│   │ Tech Blogs  │          │ GitHub API   │          │ (Future)      │  │
│   │ (27 sources)│          │ (PR/Issues)  │          │               │  │
│   └──────┬──────┘          └──────┬───────┘          └───────────────┘  │
└──────────┼────────────────────────┼──────────────────────────────────────┘
           │                        │
           ▼                        ▼
┌──────────────────┐    ┌──────────────────┐
│   blog_crawl_all │    │  github_collect  │
│   (Airflow DAG)  │    │  (Airflow DAG)   │
│                  │    │                  │
│ discover → fetch │    │ API fetch        │
│ → parse          │    │ → PR/Issue parse │
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         │  Raw HTML             │  Raw JSON
         ▼                       ▼
┌──────────────────────────────────────────┐
│            MinIO / R2 (Raw)              │
│                                          │
│  raw/{source}/{date}/{hash}.html         │
│  (원본 보존, 변환 전 저장)                 │
└──────────────────┬───────────────────────┘
                   │
                   │  articles 테이블에 파싱 결과 저장
                   ▼
┌──────────────────────────────────────────┐
│       PostgreSQL app_db (운영)            │
│                                          │
│  public.articles          (파싱된 아티클)  │
│  public.crawl_sources     (소스 정의)     │
│  public.crawl_jobs        (크롤링 추적)   │
│  public.article_enrichments (AI 결과)     │
└──────────────────┬───────────────────────┘
                   │
                   │  dlt_load DAG
                   │  (dlt ducklake destination)
                   ▼
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│                    DuckLake (Lakehouse)                       │
│                                                              │
│   Catalog: PostgreSQL (airflow_db)                           │
│   Storage: MinIO (dev) / R2 (prod) — Parquet files           │
│   Engine:  DuckDB (in-process OLAP)                          │
│                                                              │
│   ┌─────────────┐    dbt     ┌─────────────┐    dbt         │
│   │   Bronze    │ ─────────► │   Silver    │ ─────────►     │
│   │   (view)    │            │   (table)   │                 │
│   │             │            │             │                 │
│   │ stg_articles│            │ int_articles│                 │
│   └─────────────┘            │ _cleaned    │                 │
│                              └──────┬──────┘                 │
│                                     │                        │
│                          ┌──────────┼──────────┐             │
│                          │    AI Enrich DAG    │             │
│                          │  (Ollama qwen3.5)   │             │
│                          │  keywords, topics,  │             │
│                          │  summary            │             │
│                          └──────────┼──────────┘             │
│                                     │                        │
│                                     ▼           dbt          │
│                              ┌─────────────┐                 │
│                              │    Gold     │                 │
│                              │   (table)   │                 │
│                              │             │                 │
│                              │ mart_articles│                │
│                              │ mart_trending│                │
│                              │ mart_keyword │                │
│                              │ mart_source  │                │
│                              └──────┬──────┘                 │
│                                     │                        │
└─────────────────────────────────────┼────────────────────────┘
                                      │
                                      │  dbt reverse_etl
                                      │  (DuckDB postgres extension)
                                      ▼
┌──────────────────────────────────────────────────────────────┐
│              PostgreSQL app_db.serving                        │
│                                                              │
│  serving.mart_articles         (tsvector + GIN FTS)          │
│  serving.mart_trending_topics                                │
│  serving.mart_keyword_stats                                  │
│  serving.mart_source_stats                                   │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Nest.js API │
                    │  (별도 레포)  │
                    └──────────────┘
```

### DAG 실행 순서 (블로그 파이프라인)

```
blog_crawl_all (매일 00:00)
    │  articles_ready Asset
    ▼
dlt_load (매일 01:00)
    │  bronze_ready Asset
    ▼
dbt_transform (매일 02:00)
    │  silver_ready Asset
    ▼
ai_enrich (매일 03:00)
    │  enrichments_ready Asset
    ▼
dbt_gold + reverse_etl
    │  gold_ready Asset
    ▼
Nest.js API가 serving 스키마 조회
```

### GitHub 파이프라인 아키텍처

블로그 파이프라인과 동일한 원칙(Raw First, Asset 기반 체이닝, reverse_etl)을 따르되,
GitHub API 데이터는 이미 구조화되어 있으므로 Bronze/Silver 레이어를 건너뛴다.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         GitHub Pipeline                                  │
│                                                                          │
│  ┌──────────────────┐                                                   │
│  │  GitHub API      │                                                   │
│  │  (REST API v3)   │                                                   │
│  │  PAT 인증        │                                                   │
│  └────────┬─────────┘                                                   │
│           │                                                              │
│           ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │              github_collect DAG (매일 06:00)                  │       │
│  │                                                              │       │
│  │  sync_repos → get_repos → collect_repo.expand() → summarize  │       │
│  │                                                              │       │
│  │  각 repo마다:                                                 │       │
│  │  ┌─────────────────────────────────────────────────────┐     │       │
│  │  │ 1. API에서 PR/Issue JSON 수집                        │     │       │
│  │  │ 2. Raw JSON → MinIO 저장 (Raw First)                 │     │       │
│  │  │    raw/github/{owner}_{repo}/{date}/pr_{num}.json    │     │       │
│  │  │    raw/github/{owner}_{repo}/{date}/issue_{num}.json │     │       │
│  │  │ 3. 파싱 결과 → PostgreSQL 저장                        │     │       │
│  │  │    github_prs, github_issues, github_pr_files        │     │       │
│  │  └─────────────────────────────────────────────────────┘     │       │
│  └────────────────────────┬─────────────────────────────────────┘       │
│                           │                                              │
│                           │ github_collected Asset                        │
│                           ▼                                              │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │           github_ai_enrich DAG (Asset 트리거)                 │       │
│  │                                                              │       │
│  │  PostgreSQL github_prs/issues 읽기                            │       │
│  │       │                                                      │       │
│  │       ▼                                                      │       │
│  │  Ollama qwen3.5 API 호출                                     │       │
│  │  ├── PR: 요약, 핵심 변경, 영향 분석, change_type, 코드 리뷰    │       │
│  │  └── Issue: 요약, 핵심 포인트, 해결 제안, 기여 난이도          │       │
│  │       │                                                      │       │
│  │       ▼                                                      │       │
│  │  PostgreSQL 저장                                              │       │
│  │  ├── github_pr_ai_summaries                                  │       │
│  │  └── github_issue_ai_summaries                               │       │
│  └────────────────────────┬─────────────────────────────────────┘       │
│                           │                                              │
│                           │ github_enriched Asset                        │
│                           ▼                                              │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │           github_dbt_gold DAG (Asset 트리거)                  │       │
│  │                                                              │       │
│  │  ┌────────────────────────────────────────────┐              │       │
│  │  │  DuckLake Gold (dbt-duckdb)                │              │       │
│  │  │                                            │              │       │
│  │  │  app_db.github_prs                         │              │       │
│  │  │  + app_db.github_pr_ai_summaries           │              │       │
│  │  │  + app_db.github_repos                     │              │       │
│  │  │  ────────────────────────►  mart_github_prs│              │       │
│  │  │                                            │              │       │
│  │  │  app_db.github_issues                      │              │       │
│  │  │  + app_db.github_issue_ai_summaries        │              │       │
│  │  │  + app_db.github_repos                     │              │       │
│  │  │  ────────────────────────►  mart_github_   │              │       │
│  │  │                             issues         │              │       │
│  │  └────────────────────┬───────────────────────┘              │       │
│  │                       │                                      │       │
│  │                       │ reverse_etl (DuckDB postgres ext)    │       │
│  │                       ▼                                      │       │
│  │  ┌────────────────────────────────────────────┐              │       │
│  │  │  PostgreSQL app_db.serving                 │              │       │
│  │  │                                            │              │       │
│  │  │  serving.mart_github_prs   (+ FTS)         │              │       │
│  │  │  serving.mart_github_issues                │              │       │
│  │  └────────────────────────────────────────────┘              │       │
│  └────────────────────────┬─────────────────────────────────────┘       │
│                           │                                              │
│                           │ github_gold_ready Asset                      │
│                           ▼                                              │
│                    Nest.js API                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### DAG 실행 순서 (GitHub 파이프라인)

```
github_collect (매일 06:00)
    │  github_collected Asset
    ▼
github_ai_enrich (Asset 트리거)
    │  github_enriched Asset
    ▼
github_dbt_gold + reverse_etl + FTS
    │  github_gold_ready Asset
    ▼
Nest.js API가 serving 스키마 조회
```

### 블로그 vs GitHub 파이프라인 비교

| 항목 | 블로그 | GitHub |
|---|---|---|
| 데이터 소스 | RSS/웹사이트 (비구조화) | GitHub REST API (구조화) |
| Raw 저장 | HTML → MinIO | JSON → MinIO |
| Bronze/Silver | DuckLake (dlt + dbt) | 건너뜀 (API 데이터가 이미 정규화) |
| 운영 테이블 | articles, crawl_sources | github_prs, github_issues, github_repos |
| AI Enrichment | keywords, topics, summary | PR diff 분석, Issue 난이도 판단 |
| Gold source | DuckLake Silver | PostgreSQL github_* (app_db attach) |
| Gold models | mart_articles, mart_trending 등 | mart_github_prs, mart_github_issues |
| Serving | PG serving + FTS | PG serving + FTS |

### GitHub Gold 모델 설계

**mart_github_prs** — PR + AI 요약 + 레포 정보 JOIN

```
pr_id, repo_name, pr_number, title, body, state, author, labels,
created_at, updated_at, merged_at, diff_text,
ai_summary, key_changes, impact_analysis, change_type,
ai_code_review, keywords
```

**mart_github_issues** — Issue + AI 요약 + 레포 정보 JOIN

```
issue_id, repo_name, issue_number, title, body, state, author, labels,
created_at, updated_at, closed_at, linked_pr_numbers,
ai_summary, key_points, suggested_solution, contribution_difficulty,
keywords
```

### 데이터 레이어 상세

| 레이어 | 역할 | 저장소 | 포맷 | 도구 | Materialization |
|---|---|---|---|---|---|
| **Raw** | 원본 보존 | MinIO/R2 | HTML/JSON | 크롤러 | 파일 |
| **Bronze** | raw 정형화 | DuckLake | Parquet | dlt | view |
| **Silver** | 정규화/정제/dedup | DuckLake | Parquet | dbt | table |
| **Gold** | 분석/집계/서빙 준비 | DuckLake | Parquet | dbt | table |
| **Serving** | API 서빙 | PostgreSQL | table | dbt reverse_etl | table + GIN |

### 도구별 역할

```
┌────────────────────────────────────────────────────┐
│  dlt          — 추출 + Bronze 적재                   │
│                 Source: PostgreSQL articles           │
│                 Destination: DuckLake (ducklake)      │
│                 Output: Bronze Parquet on MinIO/R2    │
│                 ⚠ 순차 실행 (아래 Note 참고)           │
├────────────────────────────────────────────────────┤
│  dbt-duckdb   — 변환 (Bronze → Silver → Gold)        │
│                 Engine: DuckDB (in-memory)            │
│                 Source: DuckLake Bronze               │
│                 Target: DuckLake Silver/Gold          │
│                 Reverse ETL: Gold → PostgreSQL        │
├────────────────────────────────────────────────────┤
│  Ollama       — AI Enrichment                        │
│                 Input: DuckLake Silver                │
│                 Output: PostgreSQL enrichments        │
├────────────────────────────────────────────────────┤
│  Airflow      — 오케스트레이션                        │
│                 Asset 기반 DAG 체이닝                  │
│                 Cosmos로 dbt 실행                     │
├────────────────────────────────────────────────────┤
│  DuckDB       — 쿼리/변환 엔진                       │
│                 서버가 아닌 프로세스                    │
│                 dbt, enrich, duckdb-ui에서 사용        │
├────────────────────────────────────────────────────┤
│  DuckLake     — Lakehouse 저장 포맷                   │
│                 Catalog: PostgreSQL (airflow_db)      │
│                 Data: Parquet on MinIO/R2             │
│                 Bronze + Silver + Gold                │
└────────────────────────────────────────────────────┘
```

> **Note: dlt_load 순차 실행** — dlt ducklake destination은 PostgreSQL catalog에 `CREATE SCHEMA`를
> 실행하는데, 병렬 실행 시 race condition이 발생한다. 따라서 `dlt_load` DAG은 소스를 순차(sequential)로
> 처리하며 병렬 Dynamic Task Mapping을 사용하지 않는다.

### DuckLake 연결 방식

DuckLake catalog 연결에 두 가지 포맷이 공존한다. 혼동하지 않도록 주의.

| 사용 위치 | 포맷 | 예시 |
|---|---|---|
| **DuckDB ATTACH** (dbt profiles.yml, setup.py) | `ducklake:postgres:` + libpq params | `ducklake:postgres:dbname=airflow_db host=postgres port=5432 user=airflow password=airflow` |
| **dlt DuckLakeCredentials** (load_service.py) | `postgres://` URL | `postgres://airflow:airflow@postgres:5432/airflow_db` |

- DuckDB의 `ATTACH` 명령은 `ducklake:postgres:` 접두어 + libpq 키=값 파라미터를 사용한다
- dlt의 `DuckLakeCredentials`는 `postgres://` URL 형식을 사용한다 (`postgresql://` 아님)
- 모든 DuckLake 연결에 `METADATA_SCHEMA 'devworld_lake'`가 필수
- DuckLake alias는 `devworld_lake` (profiles.yml, setup.py 모두 동일)

### PostgreSQL 역할 분리

```
PostgreSQL (단일 RDS 인스턴스)
│
├── airflow_db
│   ├── Airflow 메타데이터 (DAG runs, task instances, ...)
│   └── DuckLake catalog (ducklake_* 메타데이터 테이블)
│
└── app_db
    ├── public 스키마 (파이프라인 운영)
    │   ├── articles              — 크롤러가 적재
    │   ├── crawl_sources         — 소스 정의
    │   ├── crawl_jobs            — 크롤링 추적
    │   ├── article_enrichments   — AI 결과
    │   ├── github_repos          — GitHub 추적 대상
    │   ├── github_prs            — PR 데이터
    │   ├── github_issues         — Issue 데이터
    │   └── github_pr_files       — PR 파일 변경
    │
    └── serving 스키마 (API 서빙) ← Nest.js가 조회
        ├── mart_articles           — tsvector + GIN FTS
        ├── mart_trending_topics
        ├── mart_keyword_stats
        ├── mart_source_stats
        ├── mart_github_prs         — tsvector + GIN FTS
        └── mart_github_issues
```

---

## 3. 인프라 아키텍처

### 로컬 개발 환경

```
┌─────────────────────────────────────────────────────┐
│                Docker Compose                        │
│                                                     │
│  ┌───────────┐  ┌───────────┐  ┌────────────────┐  │
│  │ PostgreSQL │  │   MinIO   │  │ minio-init     │  │
│  │   :5433    │  │ :9000/9001│  │ (bucket 생성)   │  │
│  │           │  │           │  └────────────────┘  │
│  │ airflow_db│  │ devworld- │                      │
│  │ app_db    │  │   raw     │                      │
│  └─────┬─────┘  │   lake    │                      │
│        │        └─────┬─────┘                      │
│        │              │                            │
│  ┌─────┴──────────────┴─────────────────────────┐  │
│  │         airflow-api-server (:8080)            │  │
│  │                                               │  │
│  │  airflow db migrate → airflow api-server      │  │
│  │  Simple Auth Manager                          │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │         airflow-scheduler                     │  │
│  │                                               │  │
│  │  LocalExecutor (프로세스 기반 태스크 실행)       │  │
│  │  api-server healthy 후 시작                    │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### DuckDB UI (로컬 개발)

DuckLake 데이터를 브라우저에서 SQL 쿼리할 수 있는 개발 도구.

```
make duckdb-ui    →   http://localhost:4213
```

- `scripts/duckdb-ui.py`를 실행하여 DuckDB UI 서버 시작
- DuckLake를 `devworld_lake`로 ATTACH + app_db를 `app_db`로 ATTACH
- Bronze/Silver/Gold 테이블 및 PostgreSQL 운영 테이블을 한 곳에서 조회 가능
- 로컬 개발/디버깅 전용, 프로덕션에서는 사용하지 않음

### 프로덕션 AWS 인프라

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AWS (ap-northeast-2)                        │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    VPC (10.0.0.0/16)                          │  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │  Public Subnets (10.0.1.0/24, 10.0.2.0/24)             │  │  │
│  │  │                                                         │  │  │
│  │  │  ┌─────────────────────────────────┐                    │  │  │
│  │  │  │       ALB (Application LB)      │ ◄── HTTPS (:443)  │  │  │
│  │  │  │                                 │     HTTP → redirect│  │  │
│  │  │  │  Target: api-server:8080        │                    │  │  │
│  │  │  └───────────────┬─────────────────┘                    │  │  │
│  │  │                  │                                      │  │  │
│  │  │  ┌───────────────┘          ┌───────────────────────┐   │  │  │
│  │  │  │ NAT Gateway              │ Internet Gateway      │   │  │  │
│  │  │  │ (ECS → 외부 접근)         │ (ALB 인바운드)         │   │  │  │
│  │  │  └───────┬───────┘          └───────────────────────┘   │  │  │
│  │  └──────────┼──────────────────────────────────────────────┘  │  │
│  │             │                                                 │  │
│  │  ┌──────────┼──────────────────────────────────────────────┐  │  │
│  │  │  Private Subnets (10.0.10.0/24, 10.0.11.0/24)          │  │  │
│  │  │                                                         │  │  │
│  │  │  ┌─────────────────┐    ┌─────────────────┐            │  │  │
│  │  │  │ ECS Fargate     │    │ ECS Fargate     │            │  │  │
│  │  │  │                 │    │                 │            │  │  │
│  │  │  │ airflow-api-    │    │ airflow-        │            │  │  │
│  │  │  │ server          │    │ scheduler       │            │  │  │
│  │  │  │                 │    │                 │            │  │  │
│  │  │  │ 512 CPU         │    │ 512 CPU         │            │  │  │
│  │  │  │ 1024 MiB        │    │ 1024 MiB        │            │  │  │
│  │  │  │                 │    │ (LocalExecutor)  │            │  │  │
│  │  │  └────────┬────────┘    └────────┬────────┘            │  │  │
│  │  │           │                      │                     │  │  │
│  │  │  ┌────────┴──────────────────────┴────────┐            │  │  │
│  │  │  │            RDS PostgreSQL 15            │            │  │  │
│  │  │  │                                        │            │  │  │
│  │  │  │  db.t3.micro, 20GB gp3                 │            │  │  │
│  │  │  │  Multi-AZ (prod)                       │            │  │  │
│  │  │  │  Backup: 7일 보존                       │            │  │  │
│  │  │  │                                        │            │  │  │
│  │  │  │  airflow_db (메타 + DuckLake catalog)   │            │  │  │
│  │  │  │  app_db (운영 + serving)                │            │  │  │
│  │  │  └────────────────────────────────────────┘            │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │       ECR        │  │ Secrets Manager  │  │   CloudWatch     │  │
│  │                  │  │                  │  │                  │  │
│  │ Airflow Docker   │  │ DB credentials   │  │ ECS logs         │  │
│  │ image            │  │ Fernet key       │  │ RDS CPU/storage  │  │
│  │                  │  │ GitHub token     │  │ ECS task alarms  │  │
│  │                  │  │ Ollama API key   │  │ SNS email 알림   │  │
│  │                  │  │ R2 credentials   │  │                  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │  Cloudflare R2   │  ◄── S3 호환 (prod Object Storage)
                    │                  │
                    │  devworld-raw    │  Raw HTML + Raw JSON (GitHub)
                    │  devworld-lake   │  DuckLake Parquet (Bronze/Silver/Gold)
                    └──────────────────┘
```

### 배포 흐름

```
Developer
    │
    │  git push
    ▼
┌──────────┐     docker build     ┌──────┐     ECS update     ┌──────────┐
│  GitHub  │ ──────────────────►  │ ECR  │ ─────────────────►  │ ECS      │
│          │                      │      │                     │ Fargate  │
└──────────┘                      └──────┘                     └──────────┘

이미지에 포함: DAGs, src/, dbt/, config/, requirements.txt
CI/CD: 미정의 (현재 수동, 향후 GitHub Actions 검토)
```

### 시크릿 관리

```
┌─────────────────────────────────────────────┐
│              환경별 시크릿 관리                │
│                                             │
│  로컬 개발                                   │
│  ├── .env 파일 (.gitignore)                  │
│  ├── AIRFLOW_CONN_* 환경변수                  │
│  └── Simple Auth Manager                    │
│                                             │
│  프로덕션                                    │
│  ├── AWS Secrets Manager                    │
│  │   ├── DB credentials (자동 생성)           │
│  │   ├── Fernet key (자동 생성)               │
│  │   ├── GitHub token (수동 설정)             │
│  │   ├── Ollama API key (수동 설정)           │
│  │   └── R2 credentials (수동 설정)           │
│  ├── ECS Task Definition에서 주입             │
│  └── FAB Auth Manager                       │
└─────────────────────────────────────────────┘
```

### 네트워크 보안

```
Internet
    │
    │  :443 (HTTPS) / :80 (→ redirect)
    ▼
┌─────────┐
│   ALB   │  ← ALB Security Group (0.0.0.0/0 :80, :443)
└────┬────┘
     │  :8080
     ▼
┌─────────┐
│   ECS   │  ← ECS Security Group (ALB에서만 :8080)
└────┬────┘
     │  :5432
     ▼
┌─────────┐
│   RDS   │  ← RDS Security Group (ECS에서만 :5432)
└─────────┘

모든 ECS/RDS는 Private Subnet에 위치.
외부 접근은 NAT Gateway 경유 (크롤링, R2, Ollama API).
```

---

## 4. 기술 스택 요약

| 카테고리 | 기술 | 용도 |
|---|---|---|
| Language | Python 3.11+ | 파이프라인 전체 |
| Orchestration | Airflow 3.1.8 | DAG 스케줄링, Asset 트리거 |
| Extract | dlt 1.19+ | PostgreSQL → DuckLake Bronze |
| Transform | dbt-duckdb 1.8+ | Bronze → Silver → Gold → reverse_etl |
| AI | Ollama Cloud (qwen3.5) | 키워드, 토픽, 요약 |
| Lakehouse | DuckLake | Parquet + PG catalog |
| Engine | DuckDB | dbt, enrich, 분석 쿼리 엔진 |
| DB | PostgreSQL 15 | 운영 + DuckLake catalog + serving |
| Object Storage | MinIO (dev) / R2 (prod) | Raw HTML, DuckLake Parquet |
| Container | Docker, ECS Fargate | Airflow 실행 환경 |
| IaC | Terraform | VPC, ECS, RDS, ALB, IAM, Secrets |
| Image Registry | ECR | Airflow Docker 이미지 |
| Monitoring | CloudWatch + SNS | 로그, 알람, 이메일 알림 |
| Auth (로컬) | Simple Auth Manager | 개발/테스트 전용 |
| Auth (프로덕션) | FAB Auth Manager | RBAC, OAuth2 지원 |
