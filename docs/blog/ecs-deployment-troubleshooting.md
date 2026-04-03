# ECS Fargate 실전 배포기: NestJS + Airflow 3.x 삽질 일지

> Docker 이미지 빌드부터 ECS 서비스 올리기, Airflow DAG 파싱까지 — 프로덕션에서 만난 모든 에러와 해결 과정을 기록합니다.
> 작성일: 2026-04-03

---

## 목차

1. [Docker 이미지 빌드 & ECR 푸시](#1-docker-이미지-빌드--ecr-푸시)
2. [ECS 서비스 배포 — 시작도 못 하는 컨테이너들](#2-ecs-서비스-배포--시작도-못-하는-컨테이너들)
3. [RDS 접속 — Private Subnet의 벽](#3-rds-접속--private-subnet의-벽)
4. [NestJS Dockerfile — pnpm 모노레포의 함정](#4-nestjs-dockerfile--pnpm-모노레포의-함정)
5. [NestJS 프로덕션 환경 설정](#5-nestjs-프로덕션-환경-설정)
6. [Airflow 3.x — DAG이 안 보이는 이유](#6-airflow-3x--dag이-안-보이는-이유)
7. [인프라 최적화 — ARM64, VPC Endpoint](#7-인프라-최적화--arm64-vpc-endpoint)
8. [Vercel 배포 — Serverless Function 12개 제한](#8-vercel-배포--serverless-function-12개-제한)
9. [남은 과제](#9-남은-과제)
10. [배운 점](#10-배운-점)

---

## 1. Docker 이미지 빌드 & ECR 푸시

### ECR 로그인

```bash
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  <ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com
```

### Apple Silicon에서 빌드할 때 주의

M1/M2 Mac에서 `docker build`를 하면 기본적으로 ARM64(linux/arm64) 이미지가 만들어집니다. ECS Fargate는 기본이 AMD64(linux/amd64)라서, `--platform`을 명시하지 않으면 이런 에러가 납니다:

```
CannotPullContainerError: image Manifest does not contain
descriptor matching platform 'linux/amd64'
```

처음에는 `--platform linux/amd64`로 빌드했다가, 나중에 ARM64 Graviton으로 전환하면서 `--platform linux/arm64`로 변경했습니다.

```bash
# AMD64 빌드 (초기)
docker build --platform linux/amd64 -t devworld-api .

# ARM64 빌드 (Graviton 전환 후)
docker build --platform linux/arm64 -t devworld-api .
```

### 빌드 → 태그 → 푸시 → 재배포 사이클

ECS 배포는 이 사이클의 반복입니다. 이 날 밤에만 10번 넘게 반복했습니다.

```bash
# 1. 빌드
docker build --platform linux/arm64 -f apps/api/Dockerfile -t devworld-api .

# 2. 태그
docker tag devworld-api:latest <ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com/devworld-api:latest

# 3. 푸시
docker push <ACCOUNT_ID>.dkr.ecr.ap-northeast-2.amazonaws.com/devworld-api:latest

# 4. ECS 재배포 (새 이미지 적용)
aws ecs update-service --cluster devworld-cluster --service devworld-nestjs-api \
  --force-new-deployment --region ap-northeast-2
```

---

## 2. ECS 서비스 배포 — 시작도 못 하는 컨테이너들

### 에러 1: Secrets Manager 권한 없음

```
AccessDeniedException: User is not authorized to perform
secretsmanager:GetSecretValue on resource: devworld/nestjs-platform-db
```

**원인**: NestJS용 시크릿 4개를 Terraform에 새로 추가했는데, IAM 정책의 Resource 목록에 안 넣었습니다.

**해결**: `iam.tf`의 `ecs_execution_secrets` 정책에 새 시크릿 ARN 추가 → `terraform apply`

**교훈**: ECS Task Definition에 시크릿을 추가할 때, **IAM 정책도 반드시 같이 업데이트**해야 합니다. Terraform plan에서는 IAM 정책 변경이 안 보여서 놓치기 쉽습니다.

### 에러 2: 이전 태스크의 캐시된 에러

IAM 정책을 수정하고 `terraform apply`를 했는데, ECS 재배포 후에도 같은 에러가 나왔습니다.

**원인**: `aws ecs list-tasks --desired-status STOPPED`로 조회하면 **이전 실패 태스크**가 나옵니다. 최신 태스크가 아닌 오래된 태스크의 에러를 보고 있었습니다.

**교훈**: STOPPED 태스크 목록에서 `createdAt` 타임스탬프를 반드시 확인해야 합니다.

### 에러 3: ENCRYPTION_KEY 환경변수 누락

```
InternalServerErrorException: ENCRYPTION_KEY environment variable is not set
```

DB 연결은 성공했지만, User AI Keys 모듈에서 API 키 암호화에 필요한 키가 없었습니다.

**해결**: Secrets Manager에 키 생성 → ECS Task Definition에 추가 → IAM 정책 업데이트 → terraform apply

```bash
aws secretsmanager create-secret \
  --name devworld/nestjs-encryption-key \
  --secret-string "$(openssl rand -hex 32)" \
  --region ap-northeast-2
```

---

## 3. RDS 접속 — Private Subnet의 벽

로컬 DB를 RDS로 마이그레이션하려면 `psql`로 RDS에 접속해야 하는데, RDS가 Private Subnet에 있어서 인터넷에서 직접 접근이 불가능합니다.

### 시도 1: RDS를 Public으로 변경 (실패)

```bash
aws rds modify-db-instance \
  --db-instance-identifier devworld-db \
  --publicly-accessible \
  --apply-immediately
```

Public IP가 할당되고 `nslookup`에도 나왔지만, **포트 연결이 안 됐습니다**. RDS가 Private Subnet AZ에 고정되어 있어서, Public IP가 있어도 Internet Gateway로의 라우팅이 없기 때문입니다.

### 시도 2: ECS Exec (실패)

실행 중인 ECS 컨테이너에 들어가서 psql을 실행하려 했지만:
- NestJS 컨테이너: DB 없어서 시작 실패 → 접속 불가
- Airflow 컨테이너: DB 없어서 시작 실패 → 접속 불가
- `TargetNotConnectedException`: SSM Agent 연결 실패

### 시도 3: EC2 Bastion + SSH 터널 (성공!)

Public Subnet에 임시 EC2를 띄우고 SSH 터널로 RDS에 접근했습니다.

```bash
# EC2 생성 (Public Subnet)
aws ec2 run-instances \
  --image-id ami-0c2d3e23e757b5d84 \
  --instance-type t3.micro \
  --key-name devworld-temp \
  --subnet-id <PUBLIC_SUBNET_ID> \
  --security-group-ids <RDS_SG_ID> \
  --associate-public-ip-address

# SSH 터널
ssh -i /tmp/devworld-temp.pem \
  -L 15432:<RDS_ENDPOINT>:5432 \
  ec2-user@<EC2_PUBLIC_IP> -N

# 새 터미널에서 RDS 접속
psql "host=localhost port=15432 dbname=airflow_db user=devworld sslmode=require"
```

**주의**: RDS는 SSL 연결을 요구합니다. `sslmode=require`를 빼먹으면:
```
FATAL: no pg_hba.conf entry for host "10.0.1.123", user "devworld",
database "airflow_db", no encryption
```

Security Group도 주의해야 합니다:
- EC2에 SSH(22번) 포트를 여는 SG가 필요
- RDS SG에 EC2 SG에서의 5432 포트 접근 허용이 필요

마이그레이션 완료 후 반드시 정리:
```bash
aws ec2 terminate-instances --instance-ids <INSTANCE_ID>
aws rds modify-db-instance --db-instance-identifier devworld-db \
  --no-publicly-accessible --apply-immediately
```

---

## 4. NestJS Dockerfile — pnpm 모노레포의 함정

이번 배포에서 **가장 많은 시간을 쓴 부분**입니다.

### 프로젝트 구조

```
devworld/ (turborepo + pnpm 모노레포)
├── apps/web/     (Next.js)
├── apps/api/     (NestJS)  ← Docker로 빌드
├── packages/ui/
├── packages/typescript-config/
└── ...
```

### 시도 1: `--filter api...` (실패)

```dockerfile
RUN pnpm install --frozen-lockfile --filter api...
```

pnpm은 의존성을 symlink + virtual store로 관리합니다. `--filter`로 설치하면 직접 의존성만 설치되고, `express` 같은 transitive dependency가 루트 `node_modules`에 안 깔립니다.

```
Error: Cannot find module 'express'
```

### 시도 2: `pnpm deploy --legacy` (실패)

```dockerfile
RUN pnpm --filter api --prod deploy --legacy /prod/api
```

pnpm deploy는 독립 실행 가능한 디렉터리를 만들어주지만, pnpm 10.x에서 `--legacy` 플래그가 필요하고, 그래도 transitive dependency가 빠졌습니다.

```bash
$ docker run --rm devworld-api ls node_modules/@nestjs/
# @nestjs/platform-express는 있지만 express 자체가 없음
```

### 시도 3: `--node-linker=hoisted` (성공!)

```dockerfile
RUN pnpm install --frozen-lockfile --node-linker=hoisted
```

**`--node-linker=hoisted`가 핵심입니다.** npm처럼 모든 의존성을 루트 `node_modules`에 flat하게 설치합니다. symlink 문제가 완전히 사라집니다.

### 최종 Dockerfile

```dockerfile
# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /app

# Stage 1: Install (hoisted flat layout)
FROM base AS deps
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY apps/api/package.json apps/api/
COPY packages/*/package.json packages/*/
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

루트에 `.dockerignore`가 없으면 로컬 `node_modules`(수 GB)가 빌드 컨텍스트에 포함되어 빌드가 실패합니다:

```
ERROR: cannot replace to directory .../node_modules/dotenv with file
```

빌드 컨텍스트 전송도 10GB → 수십 MB로 줄어듭니다.

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

### `dist/main.js` vs `dist/src/main.js`

NestJS 빌드 결과물의 경로도 문제였습니다. `nest build`의 출력이 `dist/src/main.js`에 있는데 Dockerfile CMD에서 `dist/main.js`를 참조해서:

```
Error: Cannot find module '/app/apps/api/dist/main.js'
```

`tsconfig.build.json`의 `rootDir` 설정에 따라 경로가 달라지므로, 빌드 후 실제 경로를 확인해야 합니다.

---

## 5. NestJS 프로덕션 환경 설정

### 환경변수명 불일치

ECS Task Definition에서 `DATABASE_HOST`로 주입했는데, NestJS config에서 `DB_HOST`를 읽고 있었습니다:

```typescript
// config에서 읽는 변수명
host: process.env.DB_HOST || 'localhost'
```

fallback이 `localhost`라서, 환경변수가 안 읽히면 자기 자신에 접속하려고 합니다:

```
Error: connect ECONNREFUSED 127.0.0.1:5432
```

**교훈**: `.env` 파일의 변수명과 ECS Task Definition의 변수명을 **반드시 일치**시켜야 합니다.

### RDS SSL 필수

```
FATAL: no pg_hba.conf entry for host "10.0.11.189",
user "devworld", database "app_db", no encryption
```

RDS는 기본적으로 SSL 연결을 요구합니다. TypeORM 설정에 프로덕션 SSL을 추가해야 합니다:

```typescript
const isProduction = configService.get<string>('NODE_ENV') === 'production';
return {
  type: 'postgres',
  // ...기존 설정
  ...(isProduction && { ssl: { rejectUnauthorized: false } }),
};
```

### 쿠키 Domain 설정

GitHub OAuth 로그인 후 workspace에 접근하면 계속 로그인 페이지로 리다이렉트되는 문제가 발생했습니다.

**원인**: 쿠키가 `api.devworld.cloud` 도메인으로 발급되어, `www.devworld.cloud`의 Next.js 미들웨어에서 읽을 수 없었습니다.

**해결**: 쿠키 domain을 `.devworld.cloud`로 설정하여 모든 서브도메인에서 공유:

```typescript
const cookieDomain = process.env.COOKIE_DOMAIN || undefined;
// 프로덕션: COOKIE_DOMAIN=.devworld.cloud

res.cookie('access_token', tokens.accessToken, {
  httpOnly: true,
  secure: isProduction,
  sameSite: 'lax',
  domain: cookieDomain,  // .devworld.cloud
  // ...
});
```

### CORS 설정

`www.devworld.cloud`에서 `api.devworld.cloud`로 요청할 때 CORS 에러:

```
Access to fetch at 'https://api.devworld.cloud/auth/me' from origin
'https://www.devworld.cloud' has been blocked by CORS policy
```

`FRONTEND_URL`에서 `www` 서브도메인도 자동으로 추가:

```typescript
origin: [
  'http://localhost:3001',
  process.env.FRONTEND_URL,
  process.env.FRONTEND_URL?.replace('://', '://www.'),
].filter(Boolean),
```

---

## 6. Airflow 3.x — DAG이 안 보이는 이유

### Airflow DB 초기화

Airflow가 시작되면서 첫 번째 에러:

```
ERROR: You need to initialize the database.
Please run `airflow db migrate`.
```

**해결**: `entrypoint.sh`에서 시작 전 자동으로 DB 마이그레이션:

```bash
#!/bin/bash
set -e
airflow db migrate
exec airflow "$@"
```

### Health Check 경로 — Airflow 3.x 변경

Airflow 3.x에서 health 엔드포인트가 변경되었습니다:

| Airflow 2.x | Airflow 3.x |
|---|---|
| `/health` | `/api/v2/monitor/health` |

ALB Target Group과 ECS Task Definition의 health check 경로를 모두 변경해야 했습니다. 이걸 놓치면 ALB가 컨테이너를 계속 unhealthy로 판정해서 kill합니다.

### DAG이 안 보이는 진짜 이유 — dag-processor 분리

Airflow 3.x에서 가장 큰 아키텍처 변경: **DAG 파싱이 scheduler에서 분리되었습니다.**

Airflow 2.x에서는 scheduler가 DAG 파일을 직접 파싱했지만, 3.x에서는 `dag-processor`라는 별도 프로세스가 담당합니다.

scheduler 로그에 `Filling up the DagBag`이나 `Processing file` 같은 메시지가 전혀 없었던 이유가 이것이었습니다.

### 시도 1: entrypoint에서 백그라운드 실행 (실패)

```bash
if [ "$1" = "scheduler" ]; then
  airflow dag-processor &
fi
exec airflow "$@"
```

stdout/stderr 충돌로 `ValueError: write to closed file` 에러 발생.

### 시도 2: ECS 사이드카 컨테이너 (성공!)

scheduler Task Definition에 `dag-processor`를 **사이드카 컨테이너**로 추가:

```hcl
container_definitions = jsonencode([
  {
    name    = "airflow-scheduler"
    command = ["scheduler"]
    # ...
  },
  {
    name    = "airflow-dag-processor"
    command = ["dag-processor"]
    # 같은 이미지, 같은 환경변수, 같은 시크릿
    # ...
  }
])
```

같은 Task 안의 두 컨테이너는 네트워크를 공유하므로, 별도 설정 없이 통신 가능합니다.

### dbt DAG 파싱 타임아웃

Cosmos(dbt DAG 생성 라이브러리)가 dbt 프로젝트를 파싱할 때 DuckLake DB에 연결을 시도합니다. 프로덕션 환경에서 DuckLake 연결 환경변수가 없으면 연결 타임아웃까지 기다리면서 파싱이 577초(10분)나 걸렸습니다.

**해결 1**: 파싱 타임아웃 확장

```
AIRFLOW__DAG_PROCESSOR__PARSING_TIMEOUT=120
```

**해결 2**: DuckLake 환경변수 추가

dbt `profiles.yml`이 참조하는 환경변수들을 ECS Task Definition에 모두 추가:
- `DUCKLAKE_PG_DBNAME`
- `DUCKLAKE_PG_HOST` (Secrets Manager에서)
- `POSTGRES_USER`
- `POSTGRES_PASSWORD` (Secrets Manager에서)

환경변수가 제대로 설정되자, dbt DAG 파싱 시간이 **577초 → 0.2초**로 극적으로 개선되었습니다.

### Airflow 3.x Simple Auth Manager

Airflow 3.x는 기본적으로 Simple Auth Manager를 사용합니다. 사용자/비밀번호가 시작할 때 자동 생성되고 로그에 출력됩니다:

```
Simple auth manager | Password for user 'admin': wa7WabtB7aqWhKNH
```

비밀번호가 재시작할 때마다 변경됩니다. 고정하려면 환경변수 설정이 필요합니다.

---

## 7. 인프라 최적화 — ARM64, VPC Endpoint

### ARM64 (Graviton) 전환

ECS Fargate에서 ARM64(Graviton)를 사용하면 **20% 저렴**하고 성능도 좋습니다.

Task Definition에 `runtime_platform` 추가:

```hcl
runtime_platform {
  operating_system_family = "LINUX"
  cpu_architecture        = "ARM64"
}
```

M1/M2 Mac에서는 ARM64 빌드가 네이티브라 빌드 속도도 빨라집니다. AMD64 에뮬레이션으로 빌드할 때보다 체감 2~3배 빠릅니다.

### Scheduler 리소스 업그레이드

scheduler Task에 사이드카 컨테이너(dag-processor)가 추가되면서 1 vCPU / 2GB로 업그레이드했습니다:

| 서비스 | CPU | 메모리 | 컨테이너 |
|--------|-----|--------|----------|
| NestJS API | 0.5 vCPU | 1 GB | 1개 |
| Airflow API Server | 0.5 vCPU | 1 GB | 1개 |
| Airflow Scheduler | 1 vCPU | 2 GB | 3개 (scheduler + dag-processor + api-server 예정) |

### VPC Endpoint

ECS 컨테이너가 ECR에서 이미지를 pull하거나 CloudWatch에 로그를 보낼 때 NAT Gateway를 거칩니다. NAT Gateway 데이터 전송 비용이 $0.045/GB입니다.

VPC Interface Endpoint를 쓰면 NAT를 안 거치지만, 각각 ~$7/월입니다. 현재 규모에서는 NAT 비용이 더 저렴해서 **S3 Gateway Endpoint(무료)만** 추가했습니다.

```hcl
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.ap-northeast-2.s3"
  route_table_ids = [aws_route_table.private.id]
}
```

---

## 8. Vercel 배포 — Serverless Function 12개 제한

### Hobby 플랜의 벽

Next.js 빌드는 성공했지만 배포 단계에서:

```
Error: No more than 12 Serverless Functions can be added
to a Deployment on the Hobby plan.
```

Dynamic 라우트(서버 컴포넌트)가 12개를 초과했습니다. workspace, article, series 등 서버에서 데이터를 가져오는 페이지가 많아서 발생.

**해결**: Vercel Pro 업그레이드 ($20/월). SSR/ISR 캐시, Edge 배포, 자동 CI/CD 등 Next.js 최적화가 포함되어 있어 비용 대비 효율적입니다.

### 도메인 연결

Cloudflare DNS에 추가:

| Type | Name | Target |
|------|------|--------|
| A | `@` (devworld.cloud) | 216.198.79.1 (Vercel) |
| CNAME | `www` | 947b36a3dcd2330a.vercel-dns-017.com |
| CNAME | `api` | devworld-alb-xxx.elb.amazonaws.com |
| CNAME | `airflow` | devworld-alb-xxx.elb.amazonaws.com |

---

## 9. 남은 과제

### Airflow Execution API 문제

Airflow 3.x에서 scheduler가 태스크를 실행하려면 api-server의 **Execution API**(`/execution/`)에 접근해야 합니다. 현재 scheduler와 api-server가 별도 ECS Service라서 `localhost:8080`으로 접근이 안 됩니다.

```
executor_state=failed, try_number=1, pid=None
```

**해결 방향**: scheduler Task에 api-server도 사이드카로 추가. 같은 Task 안에서는 localhost 통신이 가능합니다.

### Airflow 로그 서버

```
Could not read served logs: Invalid URL 'http://:8793/log/...'
No host supplied
```

ECS Fargate에서 컨테이너의 hostname이 비어있어서 로그 서버 주소가 생성되지 않습니다. 원격 로그 저장소(S3/R2)를 설정하면 해결됩니다.

### CI/CD

현재 수동으로 Docker build → ECR push → ECS update를 하고 있습니다. GitHub Actions로 자동화 필요:
- devworld 레포: `apps/api/**` 변경 → NestJS 자동 배포
- devworld-airflow 레포: 변경 → Airflow 자동 배포

---

## 10. 배운 점

### pnpm 모노레포 + Docker

1. **`--node-linker=hoisted`가 가장 현실적** — pnpm의 symlink 구조는 Docker 멀티스테이지 빌드와 상성이 안 좋습니다
2. **`.dockerignore`는 빌드 컨텍스트 루트에** — `apps/api/.dockerignore`가 아닌 프로젝트 루트에 있어야 합니다
3. **`pnpm deploy`는 만능이 아님** — transitive dependency를 놓칠 수 있습니다

### Airflow 3.x 프로덕션 배포

4. **dag-processor는 별도 프로세스** — Airflow 2.x와 가장 큰 차이. scheduler만 띄우면 DAG이 파싱되지 않습니다
5. **Execution API가 필수** — scheduler → api-server 통신이 필요해서, 같은 Task에 사이드카로 넣거나 Service Discovery가 필요합니다
6. **Health check 경로 변경** — `/health` → `/api/v2/monitor/health`

### ECS Fargate

7. **환경변수명 통일** — 로컬 `.env`와 ECS Task Definition의 변수명이 다르면 디버깅이 매우 어렵습니다
8. **Private Subnet의 RDS 접근은 Bastion 필수** — Public으로 바꿔도 라우팅 문제로 안 될 수 있습니다
9. **IAM 정책 업데이트를 잊지 말 것** — 시크릿 추가 시 반드시 IAM Resource 목록도 업데이트
10. **ARM64(Graviton)로 시작하는 게 나음** — 20% 저렴하고, M1/M2 Mac에서 빌드도 빠름

### 비용 최적화

11. **VPC Interface Endpoint는 규모에 따라** — 각 $7/월이라 소규모에서는 NAT가 더 저렴
12. **S3 Gateway Endpoint는 무조건** — 무료이고 NAT 트래픽 절감
13. **RDS Multi-AZ는 프리 티어에서 불가** — 초기에는 Single-AZ로 시작

---

## 비용 정리 (최종)

| 서비스 | 스펙 | 월 비용 |
|--------|------|---------|
| ECS Fargate (NestJS) | 0.5 vCPU ARM64, 1GB | ~$12 |
| ECS Fargate (Airflow API) | 0.5 vCPU ARM64, 1GB | ~$12 |
| ECS Fargate (Scheduler + dag-processor) | 1 vCPU ARM64, 2GB | ~$24 |
| RDS PostgreSQL | db.t3.micro, 20GB, Single-AZ | ~$15 |
| ALB | 기본 + 트래픽 | ~$16 |
| NAT Gateway | 기본 + 데이터 | ~$33 |
| Vercel Pro | Next.js | $20 |
| 기타 (ECR, Secrets, CloudWatch) | | ~$10 |
| **합계** | | **~$142/월** |

---

## 전체 아키텍처 (최종)

```
                    ┌─────────────┐
                    │   Vercel    │
                    │  Next.js    │
                    │devworld.cloud│
                    └──────┬──────┘
                           │
Internet ──── HTTPS ───── ALB ────┬── api.devworld.cloud ──── NestJS (ARM64)
                                  │                            ├── platform_db
                                  │                            └── app_db (serving)
                                  │
                                  └── airflow.devworld.cloud ── Airflow API
                                                                    │
                                     Scheduler Task ─────────────────┘
                                     ├── airflow-scheduler
                                     ├── airflow-dag-processor (사이드카)
                                     └── airflow-api-server (사이드카, 예정)
                                            │
                                     ┌──────┴──────┐
                                     │     RDS      │
                                     │ PostgreSQL 15│
                                     │ 3 databases  │
                                     └─────────────┘
                                            │
                                     ┌──────┴──────┐
                                     │Cloudflare R2 │
                                     │ devworld-raw │
                                     │ devworld-lake│
                                     └─────────────┘
```
