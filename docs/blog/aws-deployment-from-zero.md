# AWS 배포 준비: 계정 생성부터 SSL 인증서까지

> 개인 프로젝트 DevWorld를 AWS에 배포하기 위한 사전 준비 과정을 기록합니다.
> 작성일: 2026-04-02

---

## 배경

DevWorld는 개발자를 위한 기술 블로그 플랫폼입니다. 프론트엔드(Next.js), 백엔드 API(NestJS), 데이터 파이프라인(Airflow) 세 개의 서비스로 구성되어 있고, 프로덕션 배포를 위해 AWS 인프라를 구성해야 합니다.

### 목표 아키텍처

```
devworld.cloud          → Vercel (Next.js)
api.devworld.cloud      → ECS Fargate (NestJS)
airflow.devworld.cloud  → ECS Fargate (Airflow)
```

---

## 1. 필요한 도구 설치

배포에 필요한 CLI 도구들을 로컬에 설치합니다.

### AWS CLI

AWS 리소스를 터미널에서 관리하기 위한 도구입니다.

```bash
# macOS
brew install awscli

# 설치 확인
aws --version
# aws-cli/2.34.22 Python/3.14.3 Darwin/24.6.0
```

### Terraform

인프라를 코드로 관리(IaC)하기 위한 도구입니다. VPC, ECS, RDS 등을 `.tf` 파일로 정의하고 `terraform apply`로 생성합니다.

```bash
brew install terraform

terraform version
# Terraform v1.14.8
```

### PostgreSQL 클라이언트 (psql)

RDS에 접속해서 SQL을 실행하거나, 로컬 DB를 RDS로 마이그레이션할 때 사용합니다.

```bash
brew install postgresql@15

psql --version
# psql (PostgreSQL) 15.17
```

### 기존에 설치되어 있던 도구

- **Docker**: 27.4.0 — 컨테이너 이미지 빌드용
- **jq**: 1.7.1 — JSON 처리용

---

## 2. AWS 계정 생성 및 IAM 설정

### 2-1. AWS 계정 생성

https://aws.amazon.com 에서 계정을 생성합니다. 이메일, 신용카드, 휴대폰 인증이 필요합니다.

### 2-2. IAM 사용자 생성

보안상 Root 계정을 직접 사용하지 않고, 별도의 IAM 사용자를 만들어 사용합니다.

**생성 과정:**

1. AWS 콘솔 → 검색창에 `IAM` → IAM 서비스 접속
2. 왼쪽 메뉴 **Users** → **Create user**
3. User name: `devworld-admin`
4. **AWS Management Console 액세스 권한 제공** 체크
5. 콘솔 암호: 자동 생성된 암호 선택
6. **다음** → 권한 설정

**권한 설정:**

1. **직접 정책 연결** (Attach policies directly) 선택
2. 검색창에 `AdministratorAccess` 입력
3. **AdministratorAccess** 체크
4. **다음** → **사용자 생성**

### 2-3. Access Key 생성 (CLI용)

IAM 사용자를 만든 후, CLI에서 AWS를 사용하기 위한 Access Key를 발급합니다.

1. IAM → Users → `devworld-admin` 클릭
2. **Security credentials** 탭
3. **Access keys** → **Create access key**
4. Use case: **Command Line Interface (CLI)** 선택
5. **Create access key**

> Access key ID (`AKIA...`)와 Secret access key는 이 화면에서만 볼 수 있습니다. 반드시 메모하거나 CSV로 다운로드하세요.

### 2-4. AWS CLI에 자격 증명 등록

```bash
aws configure
```

```
AWS Access Key ID: AKIA...
AWS Secret Access Key: (발급받은 값)
Default region name: ap-northeast-2    # 서울 리전
Default output format: json
```

확인:
```bash
aws sts get-caller-identity
```

Account ID와 User ARN이 정상 출력되면 성공입니다.

---

## 3. Terraform 상태 저장용 S3 버킷

Terraform은 "어떤 인프라를 만들었는지" 상태(state)를 파일로 관리합니다. 이 파일을 S3에 저장하면 팀원 간 공유 + 실수 방지가 됩니다.

```bash
# S3 버킷 생성
aws s3api create-bucket \
  --bucket devworld-terraform-state \
  --region ap-northeast-2 \
  --create-bucket-configuration LocationConstraint=ap-northeast-2

# 버전 관리 활성화 (실수로 덮어써도 복구 가능)
aws s3api put-bucket-versioning \
  --bucket devworld-terraform-state \
  --versioning-configuration Status=Enabled

# 퍼블릭 접근 차단
aws s3api put-public-access-block \
  --bucket devworld-terraform-state \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

> 이 S3 버킷은 Terraform 전용입니다. 앱 데이터를 저장하는 Cloudflare R2와는 완전히 별개입니다.

---

## 4. 도메인 + Cloudflare + SSL 인증서

### 4-1. Cloudflare에 도메인 등록

도메인 `devworld.cloud`를 가비아에서 구매했고, DNS 관리를 Cloudflare로 위임합니다.

1. https://dash.cloudflare.com → **Add a site** → `devworld.cloud` 입력
2. **Free 플랜** 선택
3. Cloudflare가 네임서버 2개를 할당:
   - `ishaan.ns.cloudflare.com`
   - `pat.ns.cloudflare.com`

### 4-2. 가비아에서 네임서버 변경

1. 가비아 로그인 → My가비아 → 도메인 관리
2. `devworld.cloud` → 네임서버 설정
3. 기존 가비아 네임서버 3개를 삭제하고 Cloudflare 네임서버 2개로 교체:
   - 1차: `ishaan.ns.cloudflare.com`
   - 2차: `pat.ns.cloudflare.com`
4. 저장

> 네임서버 전파에 최대 48시간 걸릴 수 있지만, 보통 30분~1시간이면 Cloudflare 대시보드에서 **Active** 상태로 변경됩니다.

### 4-3. ACM SSL 인증서 요청

HTTPS를 위해 AWS Certificate Manager에서 SSL 인증서를 발급받습니다.

```bash
aws acm request-certificate \
  --domain-name devworld.cloud \
  --subject-alternative-names "*.devworld.cloud" \
  --validation-method DNS \
  --region ap-northeast-2
```

와일드카드(`*.devworld.cloud`)를 포함해서 `api.devworld.cloud`, `airflow.devworld.cloud` 모두 하나의 인증서로 커버합니다.

### 4-4. DNS 검증

ACM이 "이 도메인이 당신 것인지" 확인하기 위해 CNAME 레코드를 요구합니다.

```bash
aws acm describe-certificate \
  --certificate-arn <발급받은_ARN> \
  --region ap-northeast-2 \
  --query 'Certificate.DomainValidationOptions[*].[ResourceRecord.Name,ResourceRecord.Value]' \
  --output text
```

출력된 CNAME을 Cloudflare DNS에 추가:

1. Cloudflare → DNS → Records → **Add record**
2. Type: **CNAME**
3. Name: `_707536070086d3d0ccbf10925c9fab39` (ACM에서 준 Name에서 도메인 부분 제외)
4. Target: `_e268052adfe5d28eb14a6ff7926c8e54.jkddzztszm.acm-validations.aws.`
5. Proxy status: **DNS only** (회색 구름)
6. TTL: **Auto**
7. Save

> **왜 DNS only인가?** ACM이 이 CNAME을 직접 조회해야 하므로, Cloudflare 프록시를 거치면 검증이 실패합니다. ACM 검증 레코드는 트래픽 처리용이 아니라 도메인 소유 증명용입니다.

### 4-5. 인증서 발급 확인

```bash
aws acm describe-certificate \
  --certificate-arn <ARN> \
  --region ap-northeast-2 \
  --query 'Certificate.Status'
```

- `"PENDING_VALIDATION"`: 검증 중 (5~15분 소요)
- `"ISSUED"`: 발급 완료

---

## 5. NestJS API Dockerfile 준비

ECS Fargate에서 NestJS API를 실행하기 위해 Docker 이미지가 필요합니다. Multi-stage 빌드로 최종 이미지 크기를 최소화합니다.

```dockerfile
# ─── Stage 1: Install dependencies ───
FROM node:22-alpine AS deps
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app

COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/api/package.json apps/api/
COPY packages/ui/package.json packages/ui/
RUN pnpm install --frozen-lockfile --filter api...

# ─── Stage 2: Build ───
FROM node:22-alpine AS builder
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/api/node_modules ./apps/api/node_modules
COPY . .

RUN pnpm --filter api build

# ─── Stage 3: Production ───
FROM node:22-alpine AS runner
RUN apk add --no-cache dumb-init
WORKDIR /app

ENV NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/api/node_modules ./apps/api/node_modules
COPY --from=builder /app/apps/api/dist ./apps/api/dist
COPY apps/api/package.json ./apps/api/

EXPOSE 5500

USER node

ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "apps/api/dist/main.js"]
```

### 왜 Multi-stage인가?

| Stage | 역할 | 포함 내용 |
|-------|------|----------|
| deps | 의존성 설치 | node_modules |
| builder | TypeScript 컴파일 | dist/ |
| runner | 실행 | dist/ + node_modules만 (소스 코드 없음) |

최종 이미지에는 TypeScript 소스, 개발 의존성이 포함되지 않아 이미지 크기가 작고 보안에 유리합니다.

### dumb-init은 왜 쓰나?

Docker 컨테이너에서 Node.js가 PID 1로 실행되면 SIGTERM 시그널을 제대로 처리하지 못합니다. `dumb-init`이 PID 1 역할을 대신하여 graceful shutdown이 정상 작동합니다.

---

## 현재 진행 상태

- [x] CLI 도구 설치 (AWS CLI, Terraform, psql, Docker, jq)
- [x] AWS 계정 생성 + IAM 사용자 (`devworld-admin`)
- [x] AWS CLI 자격 증명 설정 (`aws configure`)
- [x] Terraform S3 버킷 생성
- [x] Cloudflare에 도메인 등록 + 가비아 네임서버 변경
- [x] ACM SSL 인증서 요청 + DNS 검증 CNAME 추가
- [x] NestJS Dockerfile 작성
- [ ] ACM 인증서 `ISSUED` 확인 대기 중
- [ ] `terraform.tfvars` 작성
- [ ] `terraform apply` 실행
- [ ] Docker 이미지 빌드 & ECR 푸시
- [ ] ECS 서비스 배포
- [ ] DB 마이그레이션
- [ ] DNS 연결 (api.devworld.cloud, airflow.devworld.cloud)
- [ ] Vercel 배포 (Next.js)
- [ ] CI/CD 설정 (GitHub Actions)

---

## 다음 글

> Terraform으로 VPC, ECS, RDS 인프라를 생성하고, Docker 이미지를 ECR에 푸시하여 실제 배포하는 과정을 다룹니다.
