# CLAUDE.md

## 프로젝트 개요

devworld 플랫폼의 **데이터 ETL 파이프라인 레포**.
테크 기업 블로그 크롤링 + GitHub 오픈소스 issue/PR 트래킹을 통해
인사이트/트렌드/키워드/원문 아티클을 생성한다.

이 레포에 Frontend(Next.js), Backend(Nest.js) 코드는 없다.
Frontend는 Vercel, Backend는 별도 ECS 서비스로 배포된다.

---

## 기술 스택

- **Language**: Python 3.11+
- **Orchestration**: Apache Airflow 3.1.8 (LocalExecutor)
- **Load**: dlt (ducklake destination → DuckLake Bronze)
- **Transform**: dbt-duckdb (via Astronomer Cosmos, DuckLake ATTACH)
- **AI Enrichment**: Ollama Cloud API (qwen3.5)
- **DB**: PostgreSQL (RDS) — 운영 메타데이터 + Airflow 백엔드 + DuckLake catalog + serving 스키마
- **Lakehouse**: DuckLake (catalog: PostgreSQL, storage: R2/MinIO, parquet 기반, Bronze/Silver/Gold 주 저장소)
- **Object Storage**: MinIO (dev) / Cloudflare R2 (prod)
- **Source 관리**: config/sources.yml (YAML → DB sync)
- **Infra**: AWS, ECS Fargate, Docker, Terraform, ECR, ALB, CloudWatch, Secrets Manager
- **Lint/Format**: ruff, black
- **Test**: pytest

## Airflow 실행 방식

- Executor: **LocalExecutor** (scheduler에서 직접 태스크 실행)
- 구성: api-server + scheduler (ECS Fargate 각 1개 서비스)
- Airflow 3.x: api-server (webserver 대체), Simple Auth Manager, Execution API
- **미사용**: worker, triggerer, Redis, CeleryExecutor
- **deferrable operator 전제 설계 금지**
- DAG 배포: Docker image에 포함하여 ECR push → ECS redeploy
- 전환 기준: 동시 태스크 수십 개 이상 시 CeleryExecutor + Redis 도입 검토
- 명시적 요청 없이 Redis/Celery/triggerer를 도입하지 않는다

---

## 데이터 흐름

```
crawl(discover+fetch+parse) → dlt_load(DuckLake Bronze) → dbt_transform(DuckLake Silver/Gold) → ai_enrich(keywords/topics) → dbt_reverse_etl(PostgreSQL serving) → Gold refresh
```

각 단계는 독립 DAG로 분리한다. 하나의 DAG에 여러 책임을 몰아넣지 않는다.

### DAG 구성

| DAG | 스케줄 (KST) | 역할 |
|---|---|---|
| `blog_crawl` | 수동 | 단일 소스 크롤링 |
| `blog_crawl_all` | 매일 00:00 | 전체 활성 소스 크롤링 (discover+fetch+parse) |
| `dlt_load` | 매일 01:00 | PostgreSQL articles → DuckLake Bronze (dlt ducklake destination) |
| `dbt_transform` | 매일 02:00 | DuckLake Bronze → Silver → Gold (dbt-duckdb, Cosmos) |
| `ai_enrich` | 매일 03:00 | DuckLake Silver → AI enrichment → article_enrichments (PostgreSQL) |
| `dbt_reverse_etl` | ai_enrich 후 | DuckLake Gold → PostgreSQL serving 스키마 export |

### GitHub 파이프라인 DAG

| DAG | 트리거 | 역할 |
|---|---|---|
| `github_collect` | 매일 06:00 | GitHub API로 PR/Issue 수집 + Raw parquet 적재 |
| `github_ai_enrich` | github_collect Asset | PR diff 요약, Issue 요약, 분류 |
| `github_dbt_gold` | github_ai_enrich Asset | Raw + enrichments → Gold 서빙 |

### 소스 관리

- `config/sources.yml`로 크롤링 소스 정의
- blog_crawl_all DAG 실행 시 YAML → DB 자동 sync
- RSS content:encoded 자동 판별 (있으면 RSS에서 직접 추출, 없으면 URL fetch + trafilatura)
- `crawl_config.url_filter` 지원 (특정 경로만 크롤링)
- `config/github_repos.yml`로 GitHub 추적 레포 정의 (owner/name/initial_fetch_days)
- GitHub API: PAT 인증, 증분 수집 (watermark 기반)

## 데이터 아키텍처 핵심 원칙

1. **Raw First**: 변환 전에 raw(HTML/JSON/metadata)를 반드시 먼저 저장. 원본 없이 파싱 결과만 저장하는 구조 금지
2. **재처리 가능**: 모든 단계는 raw 기준으로 replay 가능해야 한다 (bootstrap, backfill, 재파싱, 재enrichment)
3. **Thin DAG**: DAG는 orchestration만 담당. 비즈니스 로직은 Python 모듈로 분리
4. **Source별 확장**: 공통 추상화를 유지하되 source별 override 가능하게 설계
5. **Dedup은 다층**: URL dedup → content hash → near-duplicate → update/version detection. duplicate와 update를 구분할 것

## 데이터 레이어와 저장소 매핑

| 레이어 | 역할 | 저장소 | 포맷 |
|---|---|---|---|
| **Raw** | 원본 보존 | MinIO (dev) / R2 (prod) | HTML |
| **Bronze** | raw 정형화 | DuckLake (MinIO/R2) | Parquet (dlt) |
| **Silver** | 정규화/정제/dedup | DuckLake (MinIO/R2) | Parquet (dbt) |
| **Gold** | 분석/집계/서빙 준비 | DuckLake (MinIO/R2) | Parquet (dbt) |
| **Gold Serving** | 프로덕트 서빙용 | PostgreSQL (app_db.serving) | table (dbt reverse_etl) |

> Gold를 "집계 전용"으로 오해하지 말 것. 아티클 단위 서빙 데이터도 Gold에 포함.

**서빙 경로**: Raw HTML(MinIO) → 크롤러가 articles 테이블에 적재(PostgreSQL) → dlt가 DuckLake Bronze 적재 → dbt Bronze view → dbt Silver table → AI Enrich(article_enrichments) → dbt Gold table → dbt reverse_etl → PostgreSQL serving 스키마 → Nest.js API가 조회

**DuckDB/DuckLake**: DuckLake는 Bronze/Silver/Gold 레이어의 주 저장소. catalog은 PostgreSQL(airflow_db), 데이터는 R2/MinIO에 Parquet로 저장. dbt-duckdb가 DuckLake에 ATTACH하여 변환 수행. 최종 서빙 데이터는 reverse_etl로 PostgreSQL에 export.

**PostgreSQL 역할 정리**:
- `app_db`: articles(운영), crawl_sources, article_enrichments, serving 스키마(reverse_etl export — Nest.js가 조회)
- `airflow_db`: Airflow 메타데이터 + DuckLake catalog
- 운영 메타데이터 (crawl_jobs, crawl_sources)

## AI Enrichment

- **엔진**: Ollama Cloud API (qwen3.5 모델)
- **입력**: Silver 레이어의 int_articles_cleaned (title + content_text)
- **출력**: article_enrichments 테이블 (keywords, topics, summary)
- **실행**: ai_enrich DAG (dbt_transform 후, Gold refresh 전)
- **연동**: Gold mart_articles가 article_enrichments를 LEFT JOIN
- **중복 방지**: 이미 enrichment된 아티클은 자동 스킵

---

## 저장소 구조

| 레이어 | 포함 내용 |
|---|---|
| `domain` | entity, interface/protocol, 핵심 규칙 |
| `application` | use case, 서비스 흐름 (discovery, fetch, parse, load, enrich) |
| `infrastructure` | fetcher, parser, repository, storage adapter, AI client, DuckLake |
| `shared` | config, logging, normalization/hashing helper |

- domain에 infrastructure 구현 상세를 넣지 않는다
- DAG 파일에 business logic을 넣지 않는다
- shared에 source-specific 로직을 결합하지 않는다

---

## 하지 말 것

- raw와 parsed storage를 하나로 합치기
- raw source-of-truth를 version 없이 overwrite
- business logic을 DAG에 강하게 결합
- 명시적 요청 없이 Redis/Celery/triggerer 도입
- gold를 aggregation-only로 취급
- 모든 source가 같은 구조라고 가정
- single-company logic을 shared pipeline에 박기
- 필요 이상으로 인프라 복잡도 올리기
- storage key, schema 의미, dedup 의미를 조용히 변경
- dbt가 관리하는 Silver/Gold 테이블을 직접 수정하기 (dbt run으로만 갱신)
- DuckLake를 Nest.js API가 직접 조회하기 (반드시 PostgreSQL serving 스키마를 통해 서빙)

## 변경 시 원칙

- 아키텍처 영향이 큰 변경은 구현 전 설계 노트 먼저
- source-specific 동작은 격리
- 명시적으로 바뀐 게 아니면 현재 스택 가정 유지
- 헷갈리면: raw 보존이 안전한 쪽, backfill이 쉬운 쪽, 디버깅이 쉬운 쪽
