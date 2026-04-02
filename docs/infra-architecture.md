# devworld 인프라 아키텍처

**작성일**: 2026-03-31

⏺ pg_dump로 로컬 DB를 백업하고 RDS에 복원합니다.

# 1. 로컬에서 백업
pg_dump -h localhost -p 5433 -U airflow airflow_db > airflow_db.sql
pg_dump -h localhost -p 5433 -U devworld app_db > app_db.sql

# 2. RDS에 복원
psql -h devworld-db.xxxx.rds.amazonaws.com -U devworld -d airflow_db < airflow_db.sql
psql -h devworld-db.xxxx.rds.amazonaws.com -U devworld -d app_db < app_db.sql

DuckLake catalog도 airflow_db에 포함되어 있으므로 함께 이관됩니다. R2의 parquet 파일은 MinIO에서 R2로 별도 복사 필요:

# MinIO → R2 복사 (mc 사용)
mc alias set local http://localhost:9000 minioadmin minioadmin
mc alias set r2 https://<account>.r2.cloudflarestorage.com <access_key> <secret_key>

mc mirror local/devworld-raw r2/devworld-raw
mc mirror local/devworld-lake r2/devworld-lake

---

## 1. 전체 서비스 구성

```
devworld 플랫폼
├── Next.js (web)       → Vercel (프론트엔드)
├── Nest.js (api)       → ECS Fargate (백엔드 API)
└── Airflow (pipeline)  → ECS Fargate (데이터 파이프라인)
```

---

## 2. AWS 인프라 전체 구성도

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AWS (ap-northeast-2)                           │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                       VPC (10.0.0.0/16)                           │  │
│  │                                                                   │  │
│  │  ┌───────────────────────────────────────────────────────────┐    │  │
│  │  │  Public Subnets (10.0.1.0/24, 10.0.2.0/24)               │    │  │
│  │  │                                                           │    │  │
│  │  │  ┌───────────────────────────────────┐                    │    │  │
│  │  │  │           ALB                      │                   │    │  │
│  │  │  │                                   │                   │    │  │
│  │  │  │  api.devworld.cloud     → :5500     │ ◄── HTTPS (:443) │    │  │
│  │  │  │  airflow.devworld.cloud → :8080     │     + ACM 인증서  │    │  │
│  │  │  └───────────────┬───────────────────┘                    │    │  │
│  │  │                  │                                        │    │  │
│  │  │  ┌───────────────┘        ┌──────────────────────┐       │    │  │
│  │  │  │ NAT Gateway            │ Internet Gateway     │       │    │  │
│  │  │  │ (ECS → 외부 접근)       │ (ALB 인바운드)       │       │    │  │
│  │  │  └───────┬───────┘        └──────────────────────┘       │    │  │
│  │  └──────────┼────────────────────────────────────────────────┘    │  │
│  │             │                                                     │  │
│  │  ┌──────────┼────────────────────────────────────────────────┐    │  │
│  │  │  Private Subnets (10.0.10.0/24, 10.0.11.0/24)            │    │  │
│  │  │                                                           │    │  │
│  │  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐   │    │  │
│  │  │  │  ECS Fargate  │ │  ECS Fargate  │ │  ECS Fargate  │   │    │  │
│  │  │  │               │ │               │ │               │   │    │  │
│  │  │  │  nestjs-api   │ │ airflow-api-  │ │ airflow-      │   │    │  │
│  │  │  │  :5500        │ │ server :8080  │ │ scheduler     │   │    │  │
│  │  │  │               │ │               │ │               │   │    │  │
│  │  │  │  0.5 vCPU     │ │  0.5 vCPU     │ │  0.5 vCPU     │   │    │  │
│  │  │  │  1 GB         │ │  1 GB         │ │  1 GB         │   │    │  │
│  │  │  └───────┬───────┘ └───────┬───────┘ └───────┬───────┘   │    │  │
│  │  │          │                 │                  │           │    │  │
│  │  │  ┌───────┴─────────────────┴──────────────────┴───────┐   │    │  │
│  │  │  │              RDS PostgreSQL 15                      │   │    │  │
│  │  │  │              db.t3.micro, 20GB gp3                  │   │    │  │
│  │  │  │              Multi-AZ (prod)                        │   │    │  │
│  │  │  │                                                     │   │    │  │
│  │  │  │  ┌────────────┐ ┌────────────┐ ┌────────────────┐  │   │    │  │
│  │  │  │  │ airflow_db │ │  app_db    │ │  platform_db   │  │   │    │  │
│  │  │  │  │            │ │            │ │                │  │   │    │  │
│  │  │  │  │ Airflow    │ │ public:    │ │ Nest.js 자체   │  │   │    │  │
│  │  │  │  │ 메타데이터  │ │  운영 테이블│ │ 테이블         │  │   │    │  │
│  │  │  │  │            │ │            │ │ (users,        │  │   │    │  │
│  │  │  │  │ DuckLake   │ │ serving:   │ │  articles,     │  │   │    │  │
│  │  │  │  │ catalog    │ │  Gold mart │ │  comments...)  │  │   │    │  │
│  │  │  │  └────────────┘ └────────────┘ └────────────────┘  │   │    │  │
│  │  │  └─────────────────────────────────────────────────────┘   │    │  │
│  │  └────────────────────────────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │     ECR      │  │ Secrets Manager  │  │      CloudWatch          │  │
│  │              │  │                  │  │                          │  │
│  │ devworld/api │  │ DB credentials   │  │ ECS logs (30일 보존)     │  │
│  │ devworld/    │  │ Fernet key       │  │ RDS CPU/storage 알람     │  │
│  │   airflow    │  │ GitHub token     │  │ ECS task 알람            │  │
│  │              │  │ Ollama API key   │  │ SNS email 알림           │  │
│  │              │  │ R2 credentials   │  │                          │  │
│  └──────────────┘  └──────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

                 ┌──────────────────┐        ┌──────────────┐
                 │  Cloudflare R2   │        │    Vercel    │
                 │                  │        │              │
                 │ devworld-raw     │        │  Next.js     │
                 │  (HTML, JSON)    │        │  프론트엔드   │
                 │ devworld-lake    │        │              │
                 │  (DuckLake       │        └──────────────┘
                 │   Parquet)       │
                 └──────────────────┘
```

---

## 3. 서비스별 배포 방식

| 서비스 | 배포 대상 | 이미지 저장 | 트리거 | 이유 |
|---|---|---|---|---|
| Next.js | Vercel | Vercel 내장 | git push 자동 | SSR/ISR, Edge, 간편 |
| Nest.js | ECS Fargate | ECR `devworld/api` | GitHub Actions | RDS 직접 접근 필요 |
| Airflow | ECS Fargate | ECR `devworld/airflow` | GitHub Actions | RDS/R2 접근 + DAG 실행 |

---

## 4. ECR / ECS 구조

### ECR (이미지 저장소)

```
ECR (프라이빗 Docker Hub)
├── devworld/api:latest          ← Nest.js 이미지 (Node.js + 앱 코드)
└── devworld/airflow:latest      ← Airflow 이미지 (Python + DAGs + dbt + dlt)
```

### ECS (컨테이너 실행)

```
ECS Cluster (devworld-cluster)
│
├── Service: devworld-api               ← Nest.js
│   ├── Task Definition
│   │   ├── Image: ECR/devworld/api:latest
│   │   ├── CPU: 512 (0.5 vCPU)
│   │   ├── Memory: 1024 MB
│   │   ├── Port: 3000
│   │   └── Secrets: DB credentials (Secrets Manager)
│   ├── Desired Count: 1
│   └── ALB Target Group: api.devworld.cloud → :5500
│
├── Service: devworld-airflow-api-server ← Airflow UI/API
│   ├── Task Definition
│   │   ├── Image: ECR/devworld/airflow:latest
│   │   ├── Command: api-server
│   │   ├── CPU: 512, Memory: 1024
│   │   ├── Port: 8080
│   │   └── Secrets: DB, Fernet, GitHub, Ollama, R2
│   ├── Desired Count: 1
│   └── ALB Target Group: airflow.devworld.cloud → :8080
│
└── Service: devworld-airflow-scheduler  ← Airflow DAG 실행
    ├── Task Definition
    │   ├── Image: ECR/devworld/airflow:latest (같은 이미지)
    │   ├── Command: scheduler
    │   ├── CPU: 512, Memory: 1024
    │   └── Secrets: DB, Fernet, GitHub, Ollama, R2
    └── Desired Count: 1
```

---

## 5. RDS 데이터베이스 구조

하나의 RDS 인스턴스에 3개 database.

```
RDS PostgreSQL 15 (devworld-db)
│
├── airflow_db
│   ├── public 스키마
│   │   └── Airflow 메타데이터 (dag_run, task_instance, log...)
│   └── devworld_lake 스키마
│       └── DuckLake catalog (ducklake_schema, ducklake_table, ducklake_data_file...)
│
├── app_db
│   ├── public 스키마 (파이프라인 운영)
│   │   ├── articles, crawl_sources, crawl_jobs, article_enrichments
│   │   ├── github_repos, github_prs, github_pr_files, github_issues
│   │   └── github_pr_ai_summaries, github_issue_ai_summaries
│   └── serving 스키마 (Gold mart → API 서빙)
│       ├── serving_articles (+ tsvector FTS)
│       ├── serving_trending_topics
│       ├── serving_keyword_stats
│       ├── serving_source_stats
│       ├── serving_github_prs (+ tsvector FTS)
│       └── serving_github_issues
│
└── platform_db (Nest.js 플랫폼)
    └── public 스키마
        ├── users, articles (플랫폼 자체 글), comments
        ├── series, keywords, article_seo
        ├── images, notifications, messages
        └── user_ai_keys
```

### 서비스별 DB 접근

| 서비스 | database | 용도 | 권한 |
|---|---|---|---|
| Airflow | airflow_db | 메타데이터 + DuckLake catalog | read/write |
| Airflow | app_db | 크롤링 데이터 적재 + serving export | read/write |
| Nest.js | platform_db | 플랫폼 자체 데이터 | read/write |
| Nest.js | app_db (serving) | 파이프라인 Gold mart 조회 | **read-only** |
| DuckDB | airflow_db | DuckLake catalog 접근 | read/write |
| DuckDB | R2 parquet | Bronze/Silver/Gold 데이터 | read/write |

---

## 6. Object Storage

### 로컬 (MinIO)

```
MinIO (localhost:9000)
├── devworld-raw      ← Raw HTML (블로그), Raw JSON (GitHub)
└── devworld-lake     ← DuckLake Parquet (Bronze/Silver/Gold)
```

### 프로덕션 (Cloudflare R2)

```
Cloudflare R2 (S3 호환)
├── devworld-raw      ← Raw HTML, JSON
└── devworld-lake     ← DuckLake Parquet
```

전환: 환경변수만 변경 (STORAGE_ENDPOINT_URL, ACCESS_KEY, SECRET_KEY, S3_USE_SSL=true)

---

## 7. DuckLake 저장 구조

```
DuckLake = Catalog (PostgreSQL) + Data (R2/MinIO)

Catalog (airflow_db.devworld_lake 스키마):
  ├── ducklake_schema     → bronze, silver, gold, github_gold
  ├── ducklake_table      → articles, int_articles_cleaned, mart_*
  ├── ducklake_data_file  → 각 테이블의 parquet 파일 경로
  └── ducklake_snapshot   → 버전/시간 여행 메타데이터

Data (R2 devworld-lake 버킷):
  ├── bronze/articles/*.parquet
  ├── silver/int_articles_cleaned/*.parquet
  ├── gold/mart_articles/*.parquet
  ├── gold/mart_trending_topics/*.parquet
  ├── gold/mart_keyword_stats/*.parquet
  ├── gold/mart_source_stats/*.parquet
  ├── github_gold/mart_github_prs/*.parquet
  └── github_gold/mart_github_issues/*.parquet
```

---

## 8. 네트워크 보안

```
Internet
    │
    │  :443 (HTTPS) / :80 (→ HTTPS redirect)
    ▼
┌─────────┐
│   ALB   │  ← ALB Security Group
│         │     인바운드: 0.0.0.0/0 :80, :443
└────┬────┘
     │  :5500 (Nest.js) / :8080 (Airflow)
     ▼
┌─────────┐
│   ECS   │  ← ECS Security Group
│         │     인바운드: ALB에서만 :5500, :8080
└────┬────┘
     │  :5432
     ▼
┌─────────┐
│   RDS   │  ← RDS Security Group
│         │     인바운드: ECS에서만 :5432
└─────────┘

모든 ECS/RDS는 Private Subnet에 위치.
외부 접근은 NAT Gateway 경유 (R2, GitHub API, Ollama API).
```

---

## 9. 시크릿 관리

| 환경 | 방식 | 관리 대상 |
|---|---|---|
| 로컬 | `.env` 파일 (`.gitignore`) | DB 비밀번호, API 키, MinIO 자격증명 |
| 프로덕션 | AWS Secrets Manager | DB credentials, Fernet key, GitHub token, Ollama API key, R2 credentials |

프로덕션에서 ECS Task Definition이 Secrets Manager에서 값을 가져와 환경변수로 주입.

---

## 10. CI/CD 파이프라인

```
┌─────────────────────────────────────────────────────┐
│                    GitHub                             │
│                                                     │
│  devworld (모노레포)                                  │
│  ├── apps/web/** 변경  → Vercel 자동 배포             │
│  ├── apps/api/** 변경  → GitHub Actions               │
│  │   └── docker build → ECR push → ECS update        │
│  └── (docs, packages 변경 → 배포 안 함)               │
│                                                     │
│  devworld-airflow (별도 레포)                         │
│  └── ** 변경           → GitHub Actions               │
│      └── docker build → ECR push → ECS update        │
└─────────────────────────────────────────────────────┘
```

### 배포 흐름

```
개발자 → git push → GitHub Actions 자동 실행
                         │
                         ├── Docker build
                         ├── ECR push (이미지 저장)
                         ├── ECS update-service (배포 명령)
                         │
                         └── ECS Rolling Update
                              ├── 새 컨테이너 시작
                              ├── ALB 헬스체크 통과
                              ├── 트래픽 전환
                              └── 기존 컨테이너 종료
                              (다운타임 없음)
```

---

## 11. 비용 예상 (프로덕션)

| 서비스 | 스펙 | 월 예상 비용 |
|---|---|---|
| ECS Fargate (Nest.js) | 0.5 vCPU, 1 GB | ~$15 |
| ECS Fargate (Airflow API) | 0.5 vCPU, 1 GB | ~$15 |
| ECS Fargate (Airflow Scheduler) | 0.5 vCPU, 1 GB | ~$15 |
| RDS PostgreSQL | db.t3.micro, 20GB, Multi-AZ | ~$30 |
| ALB | 기본 요금 + 트래픽 | ~$16 |
| NAT Gateway | 기본 요금 + 데이터 | ~$33 |
| ECR | 이미지 저장 | ~$1 |
| Secrets Manager | 시크릿 6개 | ~$3 |
| CloudWatch | 로그 30일 | ~$5 |
| R2 | 저장 + 요청 | ~$1 (무료 티어) |
| Vercel | Next.js | 무료 (Hobby) |
| **합계** | | **~$134/월** |

---

## 12. 확장 시나리오

### 현재 → 중기

| 시점 | 변경 | 트리거 |
|---|---|---|
| DAG 동시 실행 증가 | Airflow Scheduler CPU 업그레이드 | 태스크 대기 시간 증가 |
| API 트래픽 증가 | Nest.js ECS Auto Scaling (2-4개) | ALB 응답 시간 증가 |
| DB 부하 증가 | RDS 인스턴스 업그레이드 (t3.micro → t3.small) | CPU > 80% 지속 |
| 데이터 50만 행 초과 | RDS 스토리지 자동 확장 (최대 100GB) | 스토리지 알람 |

### 중기 → 장기

| 시점 | 변경 | 트리거 |
|---|---|---|
| DAG 수십 개 동시 실행 | CeleryExecutor + Redis 도입 | LocalExecutor 한계 |
| DB 분리 필요 | RDS 인스턴스 분리 (pipeline용 / platform용) | DB 부하 경합 |
| DuckDB UI 팀 공유 | ECS에 DuckDB UI 서비스 추가 | 분석 수요 증가 |
| 글로벌 트래픽 | CloudFront CDN 추가 | 해외 응답 시간 |
