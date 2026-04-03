# AWS 인프라 구축: Terraform으로 ECS, RDS, ALB 배포하기

> DevWorld 플랫폼의 백엔드(NestJS)와 데이터 파이프라인(Airflow)을 AWS에 배포한 전체 과정을 기록합니다.
> 작성일: 2026-04-03

---

## 배경

이전 글에서 AWS 계정 생성, CLI 도구 설치, SSL 인증서 발급까지 완료했습니다. 이번에는 실제 인프라를 Terraform으로 생성하고, Docker 이미지를 빌드해서 ECS에 배포하는 과정입니다.

### 최종 아키텍처

```
Internet
    │
    ▼ HTTPS (:443)
┌─────────────────────────────────┐
│            ALB                   │
│  api.devworld.cloud → :5500     │
│  airflow.devworld.cloud → :8080 │
└──────────┬──────────────────────┘
           │ Private Subnet
    ┌──────┼──────────────┐
    │      │              │
    ▼      ▼              ▼
┌──────┐┌──────┐    ┌──────────┐
│NestJS││Airflow│    │ Airflow  │
│ API  ││  UI   │    │Scheduler │
│:5500 ││:8080  │    │          │
└──┬───┘└──┬───┘    └────┬─────┘
   │       │             │
   └───────┴─────────────┘
           │ :5432
           ▼
    ┌─────────────┐
    │     RDS      │
    │ PostgreSQL 15│
    │ 3 databases  │
    └─────────────┘
```

---

## 1. Terraform 변수 설정

`terraform.tfvars`에 인프라 스펙과 ACM 인증서 ARN을 설정합니다.

```hcl
aws_region  = "ap-northeast-2"
environment = "prod"

# ECS — 0.5 vCPU, 1GB 메모리 (초기 스펙)
api_server_cpu    = 512
api_server_memory = 1024
scheduler_cpu     = 512
scheduler_memory  = 1024
nestjs_api_cpu    = 512
nestjs_api_memory = 1024

# RDS — 최소 스펙
db_instance_class    = "db.t3.micro"
db_allocated_storage = 20

# SSL 인증서
acm_certificate_arn = "arn:aws:acm:ap-northeast-2:..."
```

### 비용 참고

| 서비스 | 스펙 | 월 비용 |
|--------|------|---------|
| ECS Fargate × 3 | 0.5 vCPU, 1GB 각 | ~$45 |
| RDS PostgreSQL | db.t3.micro, 20GB | ~$15 |
| ALB | 기본 + 트래픽 | ~$16 |
| NAT Gateway | 기본 + 데이터 | ~$33 |
| 기타 (ECR, Secrets, CloudWatch) | | ~$10 |
| **합계** | | **~$119/월** |

---

## 2. Terraform 실행

```bash
cd terraform/

# 초기화 (S3 백엔드 + 프로바이더 다운로드)
terraform init

# 설정 검증
terraform validate

# 실행 계획 미리보기
terraform plan -out=tfplan
# Plan: 73 to add

# 인프라 생성 (10~15분 소요, RDS가 가장 오래 걸림)
terraform apply tfplan
```

### Terraform이 생성하는 리소스 (73개)

| 카테고리 | 리소스 |
|---------|--------|
| 네트워크 | VPC, Public/Private 서브넷 4개, IGW, NAT Gateway |
| 로드밸런서 | ALB, Target Group 2개, HTTPS 리스너 + 호스트 라우팅 |
| 컨테이너 | ECS 클러스터, Task Definition 3개, Service 3개 |
| 데이터베이스 | RDS PostgreSQL 15 |
| 이미지 저장 | ECR 2개 (devworld-airflow, devworld-api) |
| 시크릿 | Secrets Manager 12개 |
| 모니터링 | CloudWatch 로그 2개, 알람 5개 |
| 보안 | Security Group 3개, IAM 역할 2개 |

### 프리 티어 주의사항

신규 AWS 계정에서 RDS 생성 시 에러가 발생할 수 있습니다:

```
FreeTierRestrictionError: The specified backup retention period
exceeds the maximum available to free tier customers.
```

**해결**: `rds.tf`에서 아래 설정 변경:
- `backup_retention_period`: 7 → **1**
- `multi_az`: true → **false**
- `skip_final_snapshot`: **true**

---

## 3. 시크릿 수동 설정

Terraform이 시크릿의 **틀**을 만들지만, 외부 서비스 자격증명은 수동 입력이 필요합니다.

### 자동 생성되는 것
- DB 비밀번호 (Terraform이 랜덤 생성 → Secrets Manager)
- DB 호스트/포트 (RDS 엔드포인트)
- Fernet key, Airflow secret key
- DuckLake catalog URL, App DB URL

### 수동 입력 (5개)

```bash
# 1. Cloudflare R2 자격증명
aws secretsmanager put-secret-value \
  --secret-id devworld/r2-credentials \
  --secret-string '{"access_key_id":"...","secret_access_key":"...","endpoint":"https://<ACCOUNT_ID>.r2.cloudflarestorage.com","bucket":"devworld-raw"}' \
  --region ap-northeast-2

# 2. GitHub Personal Access Token (Airflow용)
aws secretsmanager put-secret-value \
  --secret-id devworld/github-token \
  --secret-string "ghp_..." \
  --region ap-northeast-2

# 3. Ollama API Key
aws secretsmanager put-secret-value \
  --secret-id devworld/ollama-api-key \
  --secret-string "..." \
  --region ap-northeast-2

# 4. NestJS JWT Secrets (자동 생성)
aws secretsmanager put-secret-value \
  --secret-id devworld/nestjs-jwt-secrets \
  --secret-string "{\"access_secret\":\"$(openssl rand -hex 32)\",\"refresh_secret\":\"$(openssl rand -hex 32)\"}" \
  --region ap-northeast-2

# 5. NestJS GitHub OAuth (프로덕션용 OAuth App 별도 생성)
aws secretsmanager put-secret-value \
  --secret-id devworld/nestjs-github-oauth \
  --secret-string '{"client_id":"...","client_secret":"..."}' \
  --region ap-northeast-2
```

> GitHub OAuth App은 로컬 개발용과 프로덕션용을 분리합니다. 프로덕션 callback URL: `https://api.devworld.cloud/auth/github/callback`

---

## 4. NestJS Dockerfile — pnpm 모노레포 빌드의 함정

이번 배포에서 가장 많은 시행착오를 겪은 부분입니다.

### 문제: pnpm + 모노레포 + Docker

DevWorld는 turborepo + pnpm 모노레포 구조입니다:

```
devworld/
├── apps/web/     (Next.js)
├── apps/api/     (NestJS)  ← 이것만 Docker로 빌드
├── packages/ui/
├── packages/typescript-config/
└── ...
```

pnpm은 의존성을 **symlink + virtual store** 구조로 관리합니다. 일반적인 `npm install` → `COPY node_modules`가 안 되는 이유:

1. `pnpm install --filter api...`로 API만 설치하면 루트 `node_modules`에 패키지가 없음
2. `apps/api/node_modules`에는 직접 의존성만 있고, transitive dependency(express 등)가 빠짐
3. symlink가 Docker 멀티스테이지 빌드에서 깨짐

### 시도 1: `--filter api...` (실패)

```dockerfile
RUN pnpm install --frozen-lockfile --filter api...
```

결과: `/app/node_modules/express` 없음. `Cannot find module 'express'`

### 시도 2: `pnpm deploy --legacy` (실패)

```dockerfile
RUN pnpm --filter api --prod deploy --legacy /prod/api
```

결과: 직접 의존성(`@nestjs/core` 등)만 복사되고, transitive dependency(`express`)가 빠짐.

### 시도 3: `--node-linker=hoisted` (성공!)

```dockerfile
RUN pnpm install --frozen-lockfile --node-linker=hoisted
```

`--node-linker=hoisted`가 핵심입니다. npm처럼 모든 의존성을 루트 `node_modules`에 flat하게 설치합니다. symlink 문제 없음.

### 최종 Dockerfile

```dockerfile
# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /app

# Stage 1: Install dependencies (hoisted flat layout)
FROM base AS deps
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY apps/api/package.json apps/api/
COPY packages/ui/package.json packages/ui/
COPY packages/typescript-config/package.json packages/typescript-config/
COPY packages/jest-config/package.json packages/jest-config/
COPY packages/biome-config/package.json packages/biome-config/
COPY packages/tailwind-config/package.json packages/tailwind-config/
RUN pnpm install --frozen-lockfile --node-linker=hoisted

# Stage 2: Build
FROM base AS build
COPY --from=deps /app/ ./
COPY . .
RUN pnpm --filter api build

# Stage 3: Production
FROM node:22-alpine AS runner
RUN apk add --no-cache dumb-init curl
WORKDIR /app
ENV NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/apps/api/dist ./dist

EXPOSE 5500
USER node
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "dist/src/main.js"]
```

### 반드시 필요한 .dockerignore

루트에 `.dockerignore`가 없으면 로컬 `node_modules`(수 GB)가 빌드 컨텍스트에 포함됩니다:

```
**/node_modules
**/dist
**/.next
**/.turbo
*.log
.env
.env.*
!.env.example
.git
```

### 플랫폼 지정 필수 (Apple Silicon)

M1/M2 Mac에서 빌드하면 ARM 이미지가 만들어져서 ECS Fargate(AMD64)에서 실행 안 됩니다:

```bash
# 반드시 --platform linux/amd64 지정
docker build --platform linux/amd64 -f apps/api/Dockerfile -t devworld-api .
```

에러 메시지: `image Manifest does not contain descriptor matching platform 'linux/amd64'`

---

## 5. Docker 이미지 ECR 푸시

```bash
# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  845687758046.dkr.ecr.ap-northeast-2.amazonaws.com

# NestJS 이미지
docker tag devworld-api:latest 845687758046.dkr.ecr.ap-northeast-2.amazonaws.com/devworld-api:latest
docker push 845687758046.dkr.ecr.ap-northeast-2.amazonaws.com/devworld-api:latest

# Airflow 이미지
docker tag devworld-airflow:latest 845687758046.dkr.ecr.ap-northeast-2.amazonaws.com/devworld-airflow:latest
docker push 845687758046.dkr.ecr.ap-northeast-2.amazonaws.com/devworld-airflow:latest
```

---

## 6. Airflow DB 마이그레이션 문제

Airflow가 시작되면서 에러 발생:

```
ERROR: You need to initialize the database.
Please run `airflow db migrate`.
```

RDS의 `airflow_db`에 Airflow 메타데이터 테이블이 없기 때문입니다.

### 해결: entrypoint 스크립트

Dockerfile의 entrypoint에서 시작 전에 자동으로 `airflow db migrate`를 실행하도록 합니다:

```bash
#!/bin/bash
set -e
airflow db migrate
exec airflow "$@"
```

이렇게 하면:
- 최초 실행 시: 테이블 생성
- 이후 실행 시: no-op (이미 최신 상태)

---

## 7. DB 마이그레이션 — SSH 터널로 RDS 접속

로컬 PostgreSQL의 데이터를 RDS로 복사해야 하지만, RDS는 Private Subnet에 있어서 직접 접속이 안 됩니다.

### 시도 1: RDS를 Public으로 변경 (실패)

```bash
aws rds modify-db-instance \
  --db-instance-identifier devworld-db \
  --publicly-accessible \
  --apply-immediately
```

RDS가 Private Subnet AZ에 고정되어 있어서, Public IP가 할당되어도 라우팅이 안 됩니다.

### 시도 2: EC2 Bastion + SSH 터널 (성공)

Public Subnet에 임시 EC2를 띄워서 SSH 터널로 접속합니다:

```bash
# 1. 키페어 생성
aws ec2 create-key-pair --key-name devworld-temp \
  --query 'KeyMaterial' --output text > /tmp/devworld-temp.pem
chmod 400 /tmp/devworld-temp.pem

# 2. EC2 생성 (Public Subnet)
aws ec2 run-instances \
  --image-id ami-0c2d3e23e757b5d84 \
  --instance-type t3.micro \
  --key-name devworld-temp \
  --subnet-id <PUBLIC_SUBNET_ID> \
  --security-group-ids <RDS_SG_ID> \
  --associate-public-ip-address

# 3. SSH + Bastion 전용 Security Group 생성/연결
# (RDS SG만으로는 SSH 22번 포트가 안 열림)

# 4. SSH 터널 열기
ssh -i /tmp/devworld-temp.pem \
  -L 15432:<RDS_ENDPOINT>:5432 \
  ec2-user@<EC2_PUBLIC_IP> -N

# 5. 새 터미널에서 RDS 접속
psql "host=localhost port=15432 dbname=airflow_db user=devworld sslmode=require"
```

### SSL 주의사항

RDS는 기본적으로 SSL 연결을 요구합니다. `sslmode=require`를 붙여야 접속됩니다.

### 데이터 복원

```bash
# 로컬 DB 백업
pg_dump -h localhost -p 5433 -U devworld platform_db > /tmp/platform_db.sql
pg_dump -h localhost -p 5433 -U devworld app_db > /tmp/app_db.sql

# RDS에 DB 생성
psql "host=localhost port=15432 ..." -c "CREATE DATABASE platform_db;"
psql "host=localhost port=15432 ..." -c "CREATE DATABASE app_db;"

# 데이터 복원
psql "host=localhost port=15432 dbname=platform_db ..." < /tmp/platform_db.sql
psql "host=localhost port=15432 dbname=app_db ..." < /tmp/app_db.sql
```

### 정리

마이그레이션 완료 후 임시 리소스 삭제:

```bash
aws ec2 terminate-instances --instance-ids <INSTANCE_ID>
aws rds modify-db-instance --db-instance-identifier devworld-db \
  --no-publicly-accessible --apply-immediately
```

---

## 8. DNS 연결 (Cloudflare)

Cloudflare DNS에 CNAME 레코드 2개 추가:

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `api` | `devworld-alb-xxx.ap-northeast-2.elb.amazonaws.com` | DNS only |
| CNAME | `airflow` | `devworld-alb-xxx.ap-northeast-2.elb.amazonaws.com` | DNS only |

ALB가 호스트 헤더 기반으로 라우팅합니다:
- `api.devworld.cloud` → NestJS Target Group (:5500)
- `airflow.devworld.cloud` → Airflow Target Group (:8080)

---

## 9. ECS 배포 시 겪은 에러들

### 에러 1: Platform Mismatch

```
CannotPullContainerError: image Manifest does not contain
descriptor matching platform 'linux/amd64'
```

**원인**: M1 Mac에서 `--platform` 없이 빌드
**해결**: `docker build --platform linux/amd64`

### 에러 2: Secrets Manager 권한

```
AccessDeniedException: User is not authorized to perform
secretsmanager:GetSecretValue
```

**원인**: IAM 정책에 새로 추가한 시크릿 ARN이 빠짐
**해결**: `iam.tf`의 execution role 정책에 시크릿 ARN 추가 → terraform apply

### 에러 3: Module Not Found

```
Error: Cannot find module '/app/apps/api/dist/main.js'
```

**원인**: NestJS 빌드 결과가 `dist/src/main.js`에 있는데 CMD가 `dist/main.js`를 참조
**해결**: `CMD ["node", "dist/src/main.js"]`

### 에러 4: express 모듈 없음

```
Error: Cannot find module 'express'
```

**원인**: pnpm의 symlink 구조가 Docker에서 깨짐
**해결**: `--node-linker=hoisted`로 flat 설치

### 에러 5: 환경변수명 불일치

```
ERROR [TypeOrmModule] Unable to connect to the database.
Error: connect ECONNREFUSED 127.0.0.1:5432
```

**원인**: ECS Task Definition에서 `DATABASE_HOST`로 주입했는데, NestJS config에서 `DB_HOST`를 읽음 → fallback으로 `localhost` 사용
**해결**: 환경변수명을 NestJS config에 맞춤 (`DB_HOST`, `DB_PORT` 등)

### 에러 6: SSL 필수

```
no pg_hba.conf entry for host "10.0.11.189", user "devworld",
database "app_db", no encryption
```

**원인**: RDS가 SSL 연결을 요구하는데 TypeORM에 SSL 설정 없음
**해결**: `app.module.ts`에서 프로덕션일 때 `ssl: { rejectUnauthorized: false }` 추가

### 에러 7: ENCRYPTION_KEY 누락

```
ENCRYPTION_KEY environment variable is not set
```

**원인**: User AI Keys 모듈에서 필요한 암호화 키가 환경변수에 없음
**해결**: Secrets Manager에 키 생성 + ECS Task Definition에 추가

---

## 10. 최종 확인

```bash
# NestJS API
curl -s https://api.devworld.cloud/health
# {"status":"ok","info":{"database":{"status":"up"}}}

# Airflow
curl -s https://airflow.devworld.cloud/api/v2/monitor/health
# {"metadatabase":{"status":"healthy"},"scheduler":{"status":"healthy"}}
```

---

## 배운 점

1. **pnpm 모노레포 + Docker는 쉽지 않다** — `--node-linker=hoisted`가 가장 현실적인 해결책
2. **환경변수명은 통일하라** — 로컬 `.env`와 ECS Task Definition의 변수명이 다르면 찾기 어려운 버그
3. **RDS Private Subnet 접근은 Bastion이 필수** — Public으로 바꿔도 라우팅이 안 될 수 있음
4. **Apple Silicon에서 빌드할 때 `--platform linux/amd64` 필수** — 빠뜨리면 ECS에서 pull 실패
5. **SSL 설정은 프로덕션 필수** — RDS는 기본적으로 비암호화 연결을 거부
6. **Terraform apply 전에 항상 plan** — 어떤 리소스가 변경되는지 확인
7. **시크릿은 Terraform + 수동 입력 조합** — 외부 서비스 키는 자동 생성 불가

---

## 현재 진행 상태

- [x] Terraform으로 AWS 인프라 생성 (73개 리소스)
- [x] Secrets Manager 시크릿 설정 (12개)
- [x] NestJS Docker 이미지 빌드 & ECR 푸시
- [x] Airflow Docker 이미지 빌드 & ECR 푸시
- [x] 로컬 DB → RDS 마이그레이션 (platform_db, app_db)
- [x] DNS 연결 (api.devworld.cloud, airflow.devworld.cloud)
- [x] ECS 서비스 배포 완료 (NestJS, Airflow API, Scheduler)
- [x] Health check 확인
- [ ] Vercel 배포 (Next.js 프론트엔드 + devworld.cloud)
- [ ] CI/CD 설정 (GitHub Actions)
- [ ] 모니터링 알람 설정

---

## 다음 글

> Vercel에 Next.js 프론트엔드를 배포하고, devworld.cloud 도메인을 연결하는 과정을 다룹니다.
