# devworld-airflow AWS 배포 가이드

**최종 수정일**: 2026-03-31

devworld 데이터 파이프라인(Airflow)을 AWS에 배포하는 전체 과정을 단계별로 안내합니다.
이 가이드를 처음부터 끝까지 순서대로 따라하면 프로덕션 환경이 구성됩니다.

---

## 목차

| 단계 | 내용 | 예상 소요 시간 |
|------|------|--------------|
| [0. 사전 준비](#0-사전-준비-prerequisites) | 계정, 도구 설치, 외부 서비스 | 30분 |
| [1. AWS CLI 및 Terraform 설정](#1-aws-cli-및-terraform-설정) | CLI 설치, 인증, S3 백엔드 | 20분 |
| [2. terraform.tfvars 작성](#2-terraformtfvars-작성) | 변수 파일 생성 | 10분 |
| [3. Terraform 실행](#3-terraform-실행) | 인프라 생성 | 15분 |
| [4. 시크릿 수동 설정](#4-시크릿-수동-설정) | R2, GitHub, Ollama 키 입력 | 10분 |
| [5. Docker 이미지 빌드 & ECR 푸시](#5-docker-이미지-빌드--ecr-푸시) | 이미지 빌드, 푸시 | 15분 |
| [6. ECS 서비스 배포](#6-ecs-서비스-배포) | 컨테이너 시작, 헬스체크 | 10분 |
| [7. 데이터베이스 초기화 확인](#7-데이터베이스-초기화-확인) | RDS 테이블 생성 | 10분 |
| [8. Airflow UI 접속 & DAG 테스트](#8-airflow-ui-접속--dag-테스트) | 로그인, 파이프라인 테스트 | 10분 |
| [9. DNS & HTTPS 설정](#9-dns--https-설정) | 도메인 연결, SSL | 20분 |
| [10. CI/CD 설정 (GitHub Actions)](#10-cicd-설정-github-actions) | 자동 배포 파이프라인 | 20분 |
| [11. 모니터링 & 알림](#11-모니터링--알림) | CloudWatch, SNS | 10분 |
| [12. 트러블슈팅](#12-트러블슈팅) | 오류별 해결 방법 | - |
| [13. 롤백 방법](#13-롤백-방법) | 문제 발생 시 되돌리기 | - |

---

## 월 예상 비용

배포 전 비용을 확인하세요.

| 서비스 | 사양 | 월 예상 비용 |
|--------|------|-------------|
| ECS Fargate (API Server) | 0.5 vCPU, 1 GB | ~$15 |
| ECS Fargate (Scheduler) | 0.5 vCPU, 1 GB | ~$15 |
| RDS PostgreSQL | db.t3.micro, 20GB | ~$30 |
| ALB (로드밸런서) | 기본 + 트래픽 | ~$16 |
| NAT Gateway | 기본 + 데이터 | ~$33 |
| ECR (이미지 저장) | ~2GB | ~$1 |
| Secrets Manager | 시크릿 6개 | ~$3 |
| CloudWatch | 로그 30일 보존 | ~$5 |
| Cloudflare R2 | 저장 + 요청 | ~$1 (무료 티어 내) |
| **합계** | | **약 $119/월 (약 16만원)** |

---

## 0. 사전 준비 (Prerequisites)

아래 항목을 모두 준비한 후 다음 단계로 진행하세요.

### 체크리스트

- [ ] **AWS 계정** 생성 완료 (https://aws.amazon.com)
- [ ] **로컬 컴퓨터에 설치할 도구들**
  - [ ] AWS CLI v2
  - [ ] Terraform >= 1.5.0
  - [ ] Docker Desktop
  - [ ] PostgreSQL 클라이언트 (psql)
  - [ ] jq (JSON 처리 도구)
- [ ] **도메인** 1개 (예: devworld.com) - Cloudflare 또는 Route53에서 관리
- [ ] **외부 서비스 계정**
  - [ ] Cloudflare 계정 + R2 구독 활성화
  - [ ] GitHub Personal Access Token (repo, read:org, read:user 권한)
  - [ ] Ollama Cloud API 키 (qwen3.5 모델용)

### 인프라 구성도

배포가 완료되면 아래와 같은 구조가 됩니다.

```
AWS (ap-northeast-2 서울 리전)
├── VPC (10.0.0.0/16)
│   ├── Public Subnets (ALB, NAT Gateway)
│   └── Private Subnets (ECS, RDS)
│       ├── ECS Fargate: airflow-api-server (웹 UI, 포트 8080)
│       ├── ECS Fargate: airflow-scheduler (DAG 실행)
│       └── RDS PostgreSQL 15 (airflow_db, app_db, platform_db)
├── ALB → airflow.devworld.com (HTTPS)
├── ECR (Docker 이미지 저장소)
├── Secrets Manager (DB 비밀번호, API 키 등)
└── CloudWatch (로그, 알람)

외부 연동
├── Cloudflare R2 (Raw HTML, Parquet 파일 저장)
├── GitHub API (PR/Issue 수집)
└── Ollama Cloud API (AI Enrichment)
```

---

## 1. AWS CLI 및 Terraform 설정

### 1-1. AWS CLI 설치

```bash
# macOS (Homebrew)
brew install awscli

# 설치 확인
aws --version
```

**예상 출력:**
```
aws-cli/2.x.x Python/3.x.x Darwin/24.x.x source/arm64
```

### 1-2. AWS 자격 증명 설정

```bash
aws configure
```

프롬프트가 나타나면 아래 값을 입력합니다.

```
AWS Access Key ID [None]: <YOUR_AWS_ACCESS_KEY_ID>
AWS Secret Access Key [None]: <YOUR_AWS_SECRET_ACCESS_KEY>
Default region name [None]: ap-northeast-2
Default output format [None]: json
```

> **참고**: Access Key는 AWS Console > IAM > Users > Security credentials에서 생성합니다.

**확인 방법:**
```bash
aws sts get-caller-identity
```

**예상 출력:**
```json
{
    "UserId": "AIDAXXXXXXXXXXXXXXXXX",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-username"
}
```

### 1-3. Terraform 설치

```bash
# macOS (Homebrew)
brew install terraform

# 설치 확인
terraform version
```

**예상 출력:**
```
Terraform v1.x.x
```

### 1-4. jq 설치

```bash
# macOS (Homebrew)
brew install jq

# 설치 확인
jq --version
```

### 1-5. Docker Desktop 설치

Docker Desktop이 아직 없다면 https://www.docker.com/products/docker-desktop/ 에서 설치합니다.

```bash
# 설치 확인
docker --version
```

### 1-6. PostgreSQL 클라이언트 설치

```bash
# macOS (Homebrew)
brew install postgresql@15

# 설치 확인
psql --version
```

### 1-7. Terraform 상태 저장용 S3 버킷 생성

Terraform은 인프라 상태를 S3에 저장합니다. 이 버킷은 Terraform 실행 전에 미리 만들어야 합니다.

```bash
# 1. S3 버킷 생성
aws s3api create-bucket \
  --bucket devworld-terraform-state \
  --region ap-northeast-2 \
  --create-bucket-configuration LocationConstraint=ap-northeast-2
```

**예상 출력:**
```json
{
    "Location": "http://devworld-terraform-state.s3.amazonaws.com/"
}
```

```bash
# 2. 버전 관리 활성화 (실수로 상태 파일이 덮어써져도 복구 가능)
aws s3api put-bucket-versioning \
  --bucket devworld-terraform-state \
  --versioning-configuration Status=Enabled
```

```bash
# 3. 퍼블릭 접근 차단 (보안)
aws s3api put-public-access-block \
  --bucket devworld-terraform-state \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

**확인 방법:**
```bash
aws s3api head-bucket --bucket devworld-terraform-state
```

출력이 없으면 정상입니다. 오류가 나면 버킷 이름이 이미 사용 중이므로 다른 이름을 선택하세요.

> **버킷 이름 변경 시**: `terraform/main.tf` 파일의 `backend "s3"` 블록에서 `bucket` 값도 동일하게 변경해야 합니다.

### 1-8. (선택) ACM 인증서 미리 요청

HTTPS를 사용하려면 ACM(AWS Certificate Manager) 인증서가 필요합니다. DNS 검증에 시간이 걸리므로 미리 요청해두면 좋습니다.

```bash
aws acm request-certificate \
  --domain-name devworld.com \
  --subject-alternative-names "*.devworld.com" \
  --validation-method DNS \
  --region ap-northeast-2
```

**예상 출력:**
```json
{
    "CertificateArn": "arn:aws:acm:ap-northeast-2:123456789012:certificate/abcdefgh-1234-5678-abcd-123456789012"
}
```

> **이 ARN 값을 메모해두세요.** 2단계에서 `terraform.tfvars`에 입력합니다.

인증서 검증을 위한 DNS 레코드를 확인합니다.

```bash
aws acm describe-certificate \
  --certificate-arn <위에서_받은_ARN> \
  --region ap-northeast-2 \
  --query 'Certificate.DomainValidationOptions'
```

출력에 나오는 CNAME 레코드를 DNS 관리자(Cloudflare 또는 Route53)에 추가하면 인증서가 발급됩니다. 발급까지 최대 30분이 소요될 수 있습니다.

---

## 2. terraform.tfvars 작성

### 2-1. terraform.tfvars 파일 생성

프로젝트의 `terraform` 디렉토리에 변수 파일을 만듭니다.

```bash
cp /Users/gimhojun/Desktop/devworld-airflow/terraform/terraform.tfvars.example \
   /Users/gimhojun/Desktop/devworld-airflow/terraform/terraform.tfvars
```

### 2-2. 변수 값 수정

`terraform/terraform.tfvars` 파일을 열어 아래와 같이 수정합니다.

```hcl
# AWS 리전 (서울)
aws_region  = "ap-northeast-2"

# 환경 (prod / staging / dev)
environment = "prod"

# -------------------------------------------------------
# VPC (변경하지 않아도 됨)
# -------------------------------------------------------
vpc_cidr             = "10.0.0.0/16"
availability_zones   = ["ap-northeast-2a", "ap-northeast-2c"]
public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]

# -------------------------------------------------------
# ECS (변경하지 않아도 됨)
# 512 = 0.5 vCPU, 1024 = 1 GB 메모리
# -------------------------------------------------------
api_server_cpu    = 512
api_server_memory = 1024
scheduler_cpu     = 512
scheduler_memory  = 1024

# -------------------------------------------------------
# RDS (변경하지 않아도 됨)
# -------------------------------------------------------
db_instance_class    = "db.t3.micro"
db_allocated_storage = 20
db_name              = "airflow_db"
db_username          = "devworld"

# -------------------------------------------------------
# (선택) CloudWatch 알람 이메일
# 비워두면 알림이 발송되지 않습니다
# -------------------------------------------------------
alarm_email = "<YOUR_EMAIL@example.com>"

# -------------------------------------------------------
# (선택) ACM 인증서 ARN - HTTPS 사용 시 입력
# 1단계 1-8에서 받은 ARN 값을 입력합니다
# 비워두면 HTTP만 사용합니다 (나중에 추가 가능)
# -------------------------------------------------------
acm_certificate_arn = ""
```

### 변수 설명

| 변수 | 설명 | 기본값 | 변경 필요 여부 |
|------|------|--------|--------------|
| `aws_region` | AWS 리전 | `ap-northeast-2` (서울) | 보통 변경 불필요 |
| `environment` | 환경 이름 | `prod` | 원하는 환경명으로 변경 가능 |
| `vpc_cidr` | VPC 네트워크 대역 | `10.0.0.0/16` | 변경 불필요 |
| `availability_zones` | 가용 영역 2개 | 서울 2a, 2c | 변경 불필요 |
| `api_server_cpu` | API 서버 CPU | 512 (0.5 vCPU) | 부하 시 1024로 변경 |
| `api_server_memory` | API 서버 메모리 | 1024 (1 GB) | 부하 시 2048로 변경 |
| `scheduler_cpu` | 스케줄러 CPU | 512 (0.5 vCPU) | 부하 시 1024로 변경 |
| `scheduler_memory` | 스케줄러 메모리 | 1024 (1 GB) | 부하 시 2048로 변경 |
| `db_instance_class` | RDS 인스턴스 타입 | `db.t3.micro` | 부하 시 `db.t3.small`로 변경 |
| `db_allocated_storage` | RDS 스토리지 (GB) | 20 | 데이터 증가 시 확장 |
| `db_name` | 기본 DB 이름 | `airflow_db` | 변경 불필요 |
| `db_username` | DB 마스터 유저 | `devworld` | 변경 불필요 |
| `alarm_email` | 알람 수신 이메일 | `""` (비활성) | 실제 이메일 입력 권장 |
| `acm_certificate_arn` | HTTPS 인증서 ARN | `""` (HTTP만) | 9단계에서 추가 |

---

## 3. Terraform 실행

### 3-1. Terraform 초기화

```bash
cd /Users/gimhojun/Desktop/devworld-airflow/terraform

terraform init
```

**예상 출력:**
```
Initializing the backend...

Successfully configured the backend "s3"! Terraform will automatically
use this backend unless the backend configuration changes.

Initializing provider plugins...
- Finding hashicorp/aws versions matching "~> 5.0"...
- Installing hashicorp/aws v5.x.x...

Terraform has been successfully initialized!
```

> **오류 시**: S3 버킷이 없거나 AWS 자격 증명이 잘못된 경우입니다. 1-2, 1-7 단계를 확인하세요.

### 3-2. 설정 검증

```bash
terraform validate
```

**예상 출력:**
```
Success! The configuration is valid.
```

### 3-3. 실행 계획 미리보기 (dry run)

실제 리소스를 생성하기 전에 무엇이 만들어질지 확인합니다.

```bash
terraform plan -out=tfplan
```

**예상 출력 (마지막 줄):**
```
Plan: 약 30~35 to add, 0 to change, 0 to destroy.
```

생성될 주요 리소스:
- VPC, 서브넷 4개 (Public 2 + Private 2)
- Internet Gateway, NAT Gateway
- ALB (로드밸런서), Target Group
- ECS Cluster, Task Definition 2개, Service 2개
- RDS PostgreSQL 인스턴스
- ECR 리포지토리
- Secrets Manager 시크릿 6개
- CloudWatch 로그 그룹, 알람 4개
- Security Group 3개 (ALB, ECS, RDS)
- IAM 역할 2개

### 3-4. 인프라 생성

```bash
terraform apply tfplan
```

> **주의**: 이 명령은 실제 AWS 리소스를 생성하며, 비용이 발생합니다.

실행에 약 10~15분이 소요됩니다. (RDS 생성이 가장 오래 걸림)

**예상 출력 (마지막 줄):**
```
Apply complete! Resources: 약 30~35 added, 0 changed, 0 destroyed.

Outputs:

alb_dns_name = "devworld-alb-1234567890.ap-northeast-2.elb.amazonaws.com"
cloudwatch_log_group = "/ecs/devworld"
ecr_repository_url = "123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/devworld/airflow"
ecs_cluster_name = "devworld-cluster"
private_subnet_ids = ["subnet-0abc...", "subnet-0def..."]
public_subnet_ids = ["subnet-0123...", "subnet-0456..."]
rds_endpoint = "devworld-db.c9akciq32.ap-northeast-2.rds.amazonaws.com:5432"
vpc_id = "vpc-0abc..."
```

### 3-5. 출력값 저장

이후 단계에서 사용할 출력값을 저장합니다.

```bash
terraform output -json > /tmp/terraform_outputs.json
```

개별 값 확인:

```bash
# RDS 엔드포인트
terraform output rds_endpoint

# ALB DNS 이름
terraform output alb_dns_name

# ECR 저장소 URL
terraform output ecr_repository_url
```

---

## 4. 시크릿 수동 설정

Terraform이 시크릿의 **틀**을 만들었지만, 외부 서비스 자격 증명은 수동으로 입력해야 합니다.

### 4-1. R2 자격 증명 설정

Cloudflare R2 대시보드에서 API 토큰을 생성한 후 아래 명령을 실행합니다.

**R2 API 토큰 생성 방법:**
1. Cloudflare 대시보드 접속 (https://dash.cloudflare.com)
2. 좌측 메뉴 > R2 Object Storage > Overview
3. "Manage R2 API tokens" 클릭
4. "Create API token" 클릭
5. 권한: Object Read & Write
6. 생성 후 Access Key ID, Secret Access Key 복사
7. Account ID 확인 (R2 Overview 페이지 우측)

```bash
aws secretsmanager put-secret-value \
  --secret-id devworld/r2-credentials \
  --secret-string '{
    "access_key_id": "<YOUR_R2_ACCESS_KEY_ID>",
    "secret_access_key": "<YOUR_R2_SECRET_ACCESS_KEY>",
    "endpoint": "https://<YOUR_CLOUDFLARE_ACCOUNT_ID>.r2.cloudflarestorage.com",
    "bucket": "devworld-raw"
  }' \
  --region ap-northeast-2
```

> `<YOUR_CLOUDFLARE_ACCOUNT_ID>`는 Cloudflare 대시보드 R2 Overview 페이지에서 확인할 수 있습니다.

**확인 방법:**
```bash
aws secretsmanager get-secret-value \
  --secret-id devworld/r2-credentials \
  --region ap-northeast-2 \
  --query 'SecretString' \
  --output text | jq .
```

### 4-2. GitHub Personal Access Token 설정

**토큰 생성 방법:**
1. GitHub 접속 > 우측 상단 프로필 > Settings
2. 좌측 맨 아래 > Developer settings
3. Personal access tokens > Tokens (classic)
4. "Generate new token (classic)" 클릭
5. 권한 선택: `repo`, `read:org`, `read:user`
6. "Generate token" 클릭 후 `ghp_` 로 시작하는 토큰 복사

```bash
aws secretsmanager put-secret-value \
  --secret-id devworld/github-token \
  --secret-string "<YOUR_GITHUB_TOKEN>" \
  --region ap-northeast-2
```

**확인 방법:**
```bash
aws secretsmanager get-secret-value \
  --secret-id devworld/github-token \
  --region ap-northeast-2 \
  --query 'SecretString' \
  --output text
```

### 4-3. Ollama API Key 설정

**API 키 발급 방법:**
1. Ollama Cloud (https://ollama.com) 접속/로그인
2. API Keys 메뉴에서 새 키 생성
3. 키 값 복사

```bash
aws secretsmanager put-secret-value \
  --secret-id devworld/ollama-api-key \
  --secret-string "<YOUR_OLLAMA_API_KEY>" \
  --region ap-northeast-2
```

### 4-4. 모든 시크릿 확인

```bash
aws secretsmanager list-secrets \
  --filters Key=name,Values=devworld \
  --region ap-northeast-2 \
  --query 'SecretList[*].[Name,CreatedDate]' \
  --output table
```

**예상 출력:**
```
------------------------------------------------------
|                    ListSecrets                       |
+-----------------------------------+-----------------+
|  devworld/db-credentials          |  2026-03-31...  |
|  devworld/airflow-secret-key      |  2026-03-31...  |
|  devworld/airflow-fernet-key      |  2026-03-31...  |
|  devworld/github-token            |  2026-03-31...  |
|  devworld/ollama-api-key          |  2026-03-31...  |
|  devworld/r2-credentials          |  2026-03-31...  |
+-----------------------------------+-----------------+
```

6개 시크릿이 모두 보이면 정상입니다.

---

## 5. Docker 이미지 빌드 & ECR 푸시

### 5-1. Docker 이미지 빌드

```bash
cd /Users/gimhojun/Desktop/devworld-airflow

docker build -t devworld-airflow:latest .
```

빌드에 약 5~10분이 소요됩니다.

**예상 출력 (마지막 줄):**
```
=> => naming to docker.io/library/devworld-airflow:latest
```

**확인 방법:**
```bash
docker images | grep devworld-airflow
```

**예상 출력:**
```
devworld-airflow   latest   abc123def456   10 seconds ago   1.2GB
```

### 5-2. ECR 로그인

```bash
# AWS 계정 ID 가져오기
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.ap-northeast-2.amazonaws.com
```

**예상 출력:**
```
Login Succeeded
```

### 5-3. 이미지 태그 & 푸시

```bash
# ECR 저장소 URL 가져오기
cd /Users/gimhojun/Desktop/devworld-airflow/terraform
ECR_URI=$(terraform output -raw ecr_repository_url)

# 이미지 태그
docker tag devworld-airflow:latest ${ECR_URI}:latest
docker tag devworld-airflow:latest ${ECR_URI}:v1.0

# ECR로 푸시
docker push ${ECR_URI}:latest
docker push ${ECR_URI}:v1.0
```

푸시에 약 3~5분이 소요됩니다.

**확인 방법:**
```bash
aws ecr list-images \
  --repository-name devworld/airflow \
  --region ap-northeast-2 \
  --query 'imageIds[*].imageTag' \
  --output table
```

**예상 출력:**
```
-------------------
|   ListImages    |
+-----------------+
|  latest         |
|  v1.0           |
+-----------------+
```

---

## 6. ECS 서비스 배포

### 6-1. API Server 서비스 배포

```bash
aws ecs update-service \
  --cluster devworld-cluster \
  --service devworld-api-server \
  --force-new-deployment \
  --region ap-northeast-2
```

### 6-2. Scheduler 서비스 배포

```bash
aws ecs update-service \
  --cluster devworld-cluster \
  --service devworld-scheduler \
  --force-new-deployment \
  --region ap-northeast-2
```

### 6-3. 배포 상태 확인

서비스가 안정될 때까지 기다립니다 (약 3~5분).

```bash
aws ecs wait services-stable \
  --cluster devworld-cluster \
  --services devworld-api-server devworld-scheduler \
  --region ap-northeast-2
```

명령이 정상 종료되면 (출력 없이 프롬프트로 돌아오면) 배포 완료입니다.

**상세 상태 확인:**
```bash
aws ecs describe-services \
  --cluster devworld-cluster \
  --services devworld-api-server devworld-scheduler \
  --region ap-northeast-2 \
  --query 'services[*].{Name:serviceName,Status:status,Running:runningCount,Desired:desiredCount}' \
  --output table
```

**예상 출력:**
```
--------------------------------------------------------------
|                      DescribeServices                       |
+--------+---------------------------+---------+-------------+
| Desired|          Name             | Running |   Status    |
+--------+---------------------------+---------+-------------+
|  1     |  devworld-api-server      |  1      |  ACTIVE     |
|  1     |  devworld-scheduler       |  1      |  ACTIVE     |
+--------+---------------------------+---------+-------------+
```

`Running`이 `1`이고 `Status`가 `ACTIVE`이면 정상입니다.

### 6-4. 컨테이너 로그 확인

```bash
# API Server 로그 (최근 50줄)
aws logs tail /ecs/devworld --follow --region ap-northeast-2 --filter-pattern "api-server"
```

Ctrl+C로 로그 스트리밍을 종료합니다.

```bash
# Scheduler 로그 (최근 50줄)
aws logs tail /ecs/devworld --follow --region ap-northeast-2 --filter-pattern "scheduler"
```

### 6-5. 헬스체크 확인

```bash
# ALB 타겟 그룹 헬스 상태 확인
ALB_ARN=$(aws elbv2 describe-load-balancers \
  --names devworld-alb \
  --region ap-northeast-2 \
  --query 'LoadBalancers[0].LoadBalancerArn' \
  --output text)

TG_ARN=$(aws elbv2 describe-target-groups \
  --load-balancer-arn ${ALB_ARN} \
  --region ap-northeast-2 \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text)

aws elbv2 describe-target-health \
  --target-group-arn ${TG_ARN} \
  --region ap-northeast-2 \
  --query 'TargetHealthDescriptions[*].{Target:Target.Id,Health:TargetHealth.State}'
```

**예상 출력:**
```json
[
    {
        "Target": "10.0.10.xxx",
        "Health": "healthy"
    }
]
```

`Health`가 `healthy`이면 ALB가 정상적으로 트래픽을 전달하고 있습니다.

---

## 7. 데이터베이스 초기화 확인

### 7-1. RDS 접속 정보 확인

```bash
DB_HOST=$(aws secretsmanager get-secret-value \
  --secret-id devworld/db-credentials \
  --region ap-northeast-2 \
  --query 'SecretString' \
  --output text | jq -r '.host')

DB_USER=$(aws secretsmanager get-secret-value \
  --secret-id devworld/db-credentials \
  --region ap-northeast-2 \
  --query 'SecretString' \
  --output text | jq -r '.username')

DB_PASS=$(aws secretsmanager get-secret-value \
  --secret-id devworld/db-credentials \
  --region ap-northeast-2 \
  --query 'SecretString' \
  --output text | jq -r '.password')

echo "Host: $DB_HOST"
echo "User: $DB_USER"
```

> **참고**: RDS는 Private Subnet에 있어 로컬에서 직접 접속할 수 없습니다. ECS Exec을 통해 컨테이너 내부에서 접속합니다.

### 7-2. ECS Exec으로 init-db.sql 실행

```bash
# 실행 중인 API Server 태스크 ID 가져오기
TASK_ARN=$(aws ecs list-tasks \
  --cluster devworld-cluster \
  --service-name devworld-api-server \
  --region ap-northeast-2 \
  --query 'taskArns[0]' \
  --output text)

# 컨테이너 내부에 접속
aws ecs execute-command \
  --cluster devworld-cluster \
  --task ${TASK_ARN} \
  --container airflow-api-server \
  --interactive \
  --command "/bin/bash" \
  --region ap-northeast-2
```

> **참고**: ECS Exec이 활성화되어 있어야 합니다. 오류가 나면 [트러블슈팅 12-5](#12-5-ecs-exec-실패)를 참조하세요.

컨테이너 내부에서 init-db.sql 실행:

```bash
# 컨테이너 내부에서 실행
psql -h $DB_HOST -U $DB_USER -d postgres < /opt/airflow/scripts/init-db.sql
```

> init-db.sql이 Docker 이미지에 포함되어 있지 않다면, Airflow가 `airflow db migrate` 명령으로 airflow_db를 자동 초기화합니다. app_db와 platform_db는 아래 명령으로 수동 생성합니다.

```bash
# app_db, platform_db가 없는 경우 수동 생성
psql -h $DB_HOST -U $DB_USER -d postgres -c "CREATE DATABASE app_db OWNER devworld;"
psql -h $DB_HOST -U $DB_USER -d postgres -c "CREATE DATABASE platform_db OWNER devworld;"
```

### 7-3. 데이터베이스 생성 확인

```bash
# 컨테이너 내부에서 실행
psql -h $DB_HOST -U $DB_USER -d postgres -c "\l"
```

**예상 출력:**
```
                                    List of databases
    Name      |  Owner   | Encoding |   Collate   |    Ctype    | Access privileges
--------------+----------+----------+-------------+-------------+-------------------
 airflow_db   | devworld | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
 app_db       | devworld | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
 platform_db  | devworld | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
 postgres     | devworld | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
```

### 7-4. app_db 테이블 확인

```bash
# 컨테이너 내부에서 실행
psql -h $DB_HOST -U $DB_USER -d app_db -c "\dt public.*"
```

**예상 출력:**
```
              List of relations
 Schema |        Name              | Type  |  Owner
--------+--------------------------+-------+----------
 public | article_enrichments      | table | devworld
 public | articles                 | table | devworld
 public | crawl_jobs               | table | devworld
 public | crawl_sources            | table | devworld
 public | github_issue_ai_summaries| table | devworld
 public | github_issues            | table | devworld
 public | github_pr_ai_summaries   | table | devworld
 public | github_pr_files          | table | devworld
 public | github_prs               | table | devworld
 public | github_repos             | table | devworld
```

### 7-5. DuckLake 스키마 생성

```bash
# 컨테이너 내부에서 실행
psql -h $DB_HOST -U $DB_USER -d airflow_db -c \
  "CREATE SCHEMA IF NOT EXISTS devworld_lake; GRANT ALL PRIVILEGES ON SCHEMA devworld_lake TO devworld;"
```

```bash
# 컨테이너에서 나오기
exit
```

---

## 8. Airflow UI 접속 & DAG 테스트

### 8-1. Airflow UI 접속

```bash
# ALB DNS 확인
cd /Users/gimhojun/Desktop/devworld-airflow/terraform
ALB_DNS=$(terraform output -raw alb_dns_name)
echo "Airflow UI: http://${ALB_DNS}"
```

브라우저에서 위 URL로 접속합니다.

> **HTTPS 설정 전에는** `http://`로 접속합니다. 9단계 이후에는 `https://airflow.devworld.com`으로 접속합니다.

### 8-2. 로그인

**기본 설정 (Simple Auth Manager):**

ECS 환경변수에 FAB Auth Manager 설정을 하지 않았다면, Simple Auth Manager가 기본으로 활성화됩니다.

- API Server 로그에서 자동 생성된 비밀번호를 확인합니다:

```bash
aws logs filter-log-events \
  --log-group-name /ecs/devworld \
  --filter-pattern "password" \
  --region ap-northeast-2 \
  --query 'events[*].message' \
  --output text
```

**FAB Auth Manager (프로덕션 권장):**

FAB Auth Manager를 사용하는 경우, ECS Exec으로 admin 유저를 생성합니다.

```bash
TASK_ARN=$(aws ecs list-tasks \
  --cluster devworld-cluster \
  --service-name devworld-api-server \
  --region ap-northeast-2 \
  --query 'taskArns[0]' \
  --output text)

aws ecs execute-command \
  --cluster devworld-cluster \
  --task ${TASK_ARN} \
  --container airflow-api-server \
  --interactive \
  --command "/bin/bash" \
  --region ap-northeast-2
```

컨테이너 내부에서:

```bash
airflow users create \
  --username admin \
  --password <YOUR_STRONG_PASSWORD> \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@devworld.com
```

```bash
exit
```

> FAB Auth Manager 상세 설정은 `docs/auth-manager-guide.md`를 참조하세요.

### 8-3. DAG 목록 확인

Airflow UI에 로그인 후, DAGs 페이지에서 다음 DAG들이 보이는지 확인합니다:

| DAG | 역할 |
|-----|------|
| `blog_crawl` | 단일 소스 크롤링 |
| `blog_crawl_all` | 전체 활성 소스 크롤링 |
| `dlt_load` | PostgreSQL -> Bronze parquet |
| `dbt_transform` | Bronze -> Silver -> Gold |
| `ai_enrich` | AI 키워드/토픽/요약 |
| `github_collect` | GitHub PR/Issue 수집 |

### 8-4. 테스트 DAG 실행

UI에서 `blog_crawl_all` DAG의 재생 버튼을 클릭하여 실행합니다.

또는 CLI로 실행:

```bash
TASK_ARN=$(aws ecs list-tasks \
  --cluster devworld-cluster \
  --service-name devworld-api-server \
  --region ap-northeast-2 \
  --query 'taskArns[0]' \
  --output text)

aws ecs execute-command \
  --cluster devworld-cluster \
  --task ${TASK_ARN} \
  --container airflow-api-server \
  --interactive \
  --command "airflow dags trigger blog_crawl_all" \
  --region ap-northeast-2
```

### 8-5. E2E 파이프라인 확인

전체 파이프라인이 정상 동작하는지 확인합니다:

1. `blog_crawl_all` 실행 -> Airflow UI에서 "success" (녹색) 확인
2. `dlt_load` 실행 -> Bronze parquet 파일이 R2에 생성되었는지 확인
3. `dbt_transform` 실행 -> app_db의 serving 스키마에 테이블 생성 확인
4. `ai_enrich` 실행 -> article_enrichments 테이블에 데이터 생성 확인

---

## 9. DNS & HTTPS 설정

### 9-1. ACM 인증서 발급 확인

1-8단계에서 요청한 인증서의 상태를 확인합니다.

```bash
aws acm list-certificates \
  --region ap-northeast-2 \
  --query 'CertificateSummaryList[*].{Domain:DomainName,Status:Status}' \
  --output table
```

**예상 출력:**
```
--------------------------------------
|         ListCertificates           |
+------------------+-----------------+
|      Domain      |     Status      |
+------------------+-----------------+
|  devworld.com    |  ISSUED         |
+------------------+-----------------+
```

Status가 `ISSUED`가 아니면, DNS 검증 레코드를 추가하지 않은 것입니다. 1-8단계를 다시 확인하세요.

### 9-2. terraform.tfvars에 인증서 ARN 추가

```bash
# 인증서 ARN 확인
aws acm list-certificates \
  --region ap-northeast-2 \
  --query 'CertificateSummaryList[0].CertificateArn' \
  --output text
```

`terraform/terraform.tfvars` 파일에서 `acm_certificate_arn` 값을 수정합니다:

```hcl
acm_certificate_arn = "arn:aws:acm:ap-northeast-2:123456789012:certificate/abcdefgh-1234-5678-abcd-123456789012"
```

### 9-3. Terraform 재적용

```bash
cd /Users/gimhojun/Desktop/devworld-airflow/terraform

terraform plan -out=tfplan
terraform apply tfplan
```

이 명령은 HTTPS 리스너를 추가하고 HTTP를 HTTPS로 리다이렉트 설정합니다.

### 9-4. DNS 레코드 생성

#### 방법 A: Cloudflare (권장)

```bash
# ALB DNS 이름 확인
cd /Users/gimhojun/Desktop/devworld-airflow/terraform
ALB_DNS=$(terraform output -raw alb_dns_name)
echo "ALB DNS: ${ALB_DNS}"
```

Cloudflare 대시보드에서:
1. DNS > Records 메뉴 이동
2. "Add Record" 클릭
3. 아래와 같이 설정:

| Type | Name | Target | Proxy status |
|------|------|--------|-------------|
| CNAME | airflow | `<ALB_DNS 출력값>` | DNS only (회색 구름) |

> **주의**: Proxy status는 "DNS only" (회색 구름)로 설정하세요. Cloudflare 프록시를 사용하면 ALB와 충돌할 수 있습니다.

#### 방법 B: Route53

```bash
# Hosted Zone ID 가져오기
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name devworld.com \
  --query 'HostedZones[0].Id' \
  --output text | cut -d'/' -f3)

ALB_DNS=$(terraform output -raw alb_dns_name)

# A 레코드 (Alias) 생성
aws route53 change-resource-record-sets \
  --hosted-zone-id ${HOSTED_ZONE_ID} \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "airflow.devworld.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "ZWKZPGTI48KDX",
          "DNSName": "'${ALB_DNS}'",
          "EvaluateTargetHealth": false
        }
      }
    }]
  }'
```

> **참고**: `HostedZoneId`의 `ZWKZPGTI48KDX`는 ap-northeast-2 리전의 ALB hosted zone ID입니다.

### 9-5. HTTPS 접속 확인

DNS 전파에 최대 5분이 소요됩니다.

```bash
# HTTP -> HTTPS 리다이렉트 확인
curl -I http://airflow.devworld.com
```

**예상 출력:**
```
HTTP/1.1 301 Moved Permanently
Location: https://airflow.devworld.com:443/
```

```bash
# HTTPS 접속 확인
curl -I https://airflow.devworld.com
```

**예상 출력:**
```
HTTP/2 200
```

브라우저에서 `https://airflow.devworld.com`으로 접속하여 Airflow UI가 정상적으로 표시되는지 확인합니다.

---

## 10. CI/CD 설정 (GitHub Actions)

### 10-1. GitHub Actions 워크플로우 파일 생성

프로젝트 루트에 `.github/workflows/deploy.yml` 파일을 생성합니다.

```yaml
# .github/workflows/deploy.yml
name: Deploy to AWS ECS

on:
  push:
    branches:
      - main
    paths:
      - 'src/**'
      - 'dags/**'
      - 'dbt/**'
      - 'config/**'
      - 'requirements.txt'
      - 'Dockerfile'

env:
  AWS_REGION: ap-northeast-2
  ECR_REPOSITORY: devworld/airflow
  ECS_CLUSTER: devworld-cluster
  IMAGE_TAG: ${{ github.sha }}

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:latest .
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:latest \
            $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG

      - name: Update ECS services
        run: |
          aws ecs update-service \
            --cluster $ECS_CLUSTER \
            --service devworld-api-server \
            --force-new-deployment \
            --region $AWS_REGION

          aws ecs update-service \
            --cluster $ECS_CLUSTER \
            --service devworld-scheduler \
            --force-new-deployment \
            --region $AWS_REGION

      - name: Wait for deployment
        run: |
          aws ecs wait services-stable \
            --cluster $ECS_CLUSTER \
            --services devworld-api-server devworld-scheduler \
            --region $AWS_REGION
```

### 10-2. GitHub OIDC Provider 생성 (IAM)

GitHub Actions가 AWS에 안전하게 접근하기 위해 OIDC Provider를 설정합니다.

```bash
# 1. OIDC Provider가 이미 있는지 확인
aws iam list-open-id-connect-providers

# 2. 없으면 생성
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"
```

### 10-3. GitHub Actions용 IAM Role 생성

```bash
# AWS 계정 ID 확인
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Trust Policy 파일 생성
cat > /tmp/github-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:<YOUR_GITHUB_ORG>/devworld-airflow:ref:refs/heads/main"
        }
      }
    }
  ]
}
EOF
```

> `<YOUR_GITHUB_ORG>`를 실제 GitHub 조직명 또는 사용자명으로 변경하세요.

```bash
# IAM Role 생성
aws iam create-role \
  --role-name GitHubActionsDeployRole \
  --assume-role-policy-document file:///tmp/github-trust-policy.json

# ECR 푸시 권한 부여
aws iam attach-role-policy \
  --role-name GitHubActionsDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

# ECS 배포 권한 부여
aws iam attach-role-policy \
  --role-name GitHubActionsDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess

# Role ARN 확인
aws iam get-role \
  --role-name GitHubActionsDeployRole \
  --query 'Role.Arn' \
  --output text
```

**예상 출력:**
```
arn:aws:iam::123456789012:role/GitHubActionsDeployRole
```

### 10-4. GitHub Secrets 설정

GitHub 레포지토리의 Settings > Secrets and variables > Actions에서 다음 시크릿을 추가합니다:

| Secret Name | 값 | 예시 |
|-------------|---|------|
| `AWS_ROLE_ARN` | 10-3에서 생성한 Role ARN | `arn:aws:iam::123456789012:role/GitHubActionsDeployRole` |

### 10-5. 자동 배포 테스트

```bash
cd /Users/gimhojun/Desktop/devworld-airflow

git add .github/workflows/deploy.yml
git commit -m "Add GitHub Actions deploy workflow"
git push origin main
```

GitHub 레포지토리의 Actions 탭에서 워크플로우 실행을 확인합니다.

**확인 항목:**
- [ ] Build 단계 성공 (Docker 이미지 빌드)
- [ ] Push 단계 성공 (ECR에 이미지 업로드)
- [ ] Deploy 단계 성공 (ECS 서비스 업데이트)
- [ ] Wait 단계 성공 (서비스 안정화)

---

## 11. 모니터링 & 알림

### 11-1. CloudWatch 알람 확인

Terraform이 자동으로 4개의 알람을 생성했습니다:

| 알람 | 조건 | 의미 |
|------|------|------|
| `devworld-rds-cpu-high` | RDS CPU > 80% (5분 평균, 3회 연속) | DB 부하 과다 |
| `devworld-rds-storage-low` | RDS 여유 스토리지 < 2GB | 디스크 공간 부족 |
| `devworld-api-server-not-running` | API Server 실행 태스크 < 1 | 웹 UI 다운 |
| `devworld-scheduler-not-running` | Scheduler 실행 태스크 < 1 | DAG 실행 중단 |

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix devworld \
  --region ap-northeast-2 \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue}' \
  --output table
```

**예상 출력:**
```
---------------------------------------------------------
|                    DescribeAlarms                       |
+----------------------------------------+--------------+
|                  Name                  |    State     |
+----------------------------------------+--------------+
|  devworld-rds-cpu-high                 |  OK          |
|  devworld-rds-storage-low              |  OK          |
|  devworld-api-server-not-running       |  OK          |
|  devworld-scheduler-not-running        |  OK          |
+----------------------------------------+--------------+
```

모두 `OK`이면 정상입니다.

### 11-2. SNS 이메일 구독 확인

`terraform.tfvars`에 `alarm_email`을 설정했다면, 해당 이메일로 구독 확인 메일이 발송됩니다.

1. 이메일 수신함에서 "AWS Notification - Subscription Confirmation" 메일 확인
2. "Confirm subscription" 링크 클릭

구독이 완료되면 알람 발생 시 이메일을 받게 됩니다.

### 11-3. 주요 모니터링 항목

일상적으로 확인할 항목:

| 항목 | 확인 방법 | 정상 기준 |
|------|----------|----------|
| ECS 서비스 상태 | AWS Console > ECS > Clusters > devworld-cluster | Running: 1/1 |
| Airflow DAG 실행 | Airflow UI > DAGs | 최근 실행 결과 녹색 |
| RDS CPU | AWS Console > RDS > Monitoring | < 80% |
| RDS 스토리지 | AWS Console > RDS > Monitoring | 여유 공간 > 2GB |
| CloudWatch 로그 | AWS Console > CloudWatch > Log groups > /ecs/devworld | 에러 없음 |

---

## 12. 트러블슈팅

### 12-1. ECS 컨테이너 시작 실패

**증상**: ECS 서비스의 Running count가 0으로 유지됨

**진단:**
```bash
# 최근 중지된 태스크 확인
aws ecs list-tasks \
  --cluster devworld-cluster \
  --service-name devworld-api-server \
  --desired-status STOPPED \
  --region ap-northeast-2 \
  --query 'taskArns[0]' \
  --output text
```

```bash
# 중지 이유 확인
STOPPED_TASK=$(aws ecs list-tasks \
  --cluster devworld-cluster \
  --service-name devworld-api-server \
  --desired-status STOPPED \
  --region ap-northeast-2 \
  --query 'taskArns[0]' \
  --output text)

aws ecs describe-tasks \
  --cluster devworld-cluster \
  --tasks ${STOPPED_TASK} \
  --region ap-northeast-2 \
  --query 'tasks[0].{StopCode:stopCode,StoppedReason:stoppedReason,Containers:containers[*].{Name:name,ExitCode:exitCode,Reason:reason}}'
```

**자주 발생하는 원인과 해결:**

| 원인 | StoppedReason 키워드 | 해결 |
|------|---------------------|------|
| 이미지 없음 | `CannotPullContainerError` | ECR에 이미지가 푸시되었는지 확인 (5단계) |
| 시크릿 접근 불가 | `ResourceInitializationError` | IAM 정책에 시크릿 ARN이 포함되었는지 확인 |
| 메모리 부족 | `OutOfMemoryError` | `terraform.tfvars`에서 메모리를 2048로 증가 |
| DB 연결 실패 | 로그에 `OperationalError` | Security Group, RDS 엔드포인트 확인 |

### 12-2. RDS 연결 실패

**증상**: Airflow 로그에 "could not connect to server" 또는 "OperationalError"

**진단:**
```bash
# Security Group 확인
# RDS SG가 ECS SG에서 포트 5432 인바운드를 허용하는지 확인

aws ec2 describe-security-groups \
  --filters Name=group-name,Values='*rds*' \
  --region ap-northeast-2 \
  --query 'SecurityGroups[*].{GroupId:GroupId,InboundRules:IpPermissions[*].{Port:FromPort,Source:UserIdGroupPairs[*].GroupId}}'
```

**해결:**
1. RDS Security Group이 ECS Security Group의 포트 5432를 허용하는지 확인
2. ECS가 Private Subnet에 배치되어 있는지 확인
3. DB 비밀번호가 Secrets Manager에 올바르게 저장되어 있는지 확인:

```bash
aws secretsmanager get-secret-value \
  --secret-id devworld/db-credentials \
  --region ap-northeast-2 \
  --query 'SecretString' \
  --output text | jq '.host'
```

### 12-3. DAG 실행 실패

**증상**: Airflow UI에서 DAG이 빨간색(Failed)으로 표시

**진단:**
1. Airflow UI > DAGs > 해당 DAG 클릭 > 실패한 Task 클릭 > Logs 탭
2. 또는 CloudWatch에서 확인:

```bash
aws logs filter-log-events \
  --log-group-name /ecs/devworld \
  --filter-pattern "ERROR" \
  --start-time $(date -v-1H +%s000) \
  --region ap-northeast-2 \
  --query 'events[*].message' \
  --output text
```

**자주 발생하는 원인:**

| 원인 | 에러 메시지 | 해결 |
|------|-----------|------|
| R2 접속 실패 | `botocore.exceptions.ClientError` | R2 자격 증명 확인 (4-1 단계) |
| GitHub API 제한 | `403 rate limit exceeded` | GitHub Token 확인, 요청 간격 조정 |
| Ollama API 실패 | `ConnectionError` | Ollama API Key 확인, 서비스 상태 확인 |
| dbt 실행 실패 | `dbt.exceptions.CompilationError` | dbt 모델 파일 구문 확인 |

### 12-4. DuckLake 연결 오류

**증상**: DuckLake 관련 DAG에서 "catalog connection failed" 등의 오류

**진단:**
```bash
# airflow_db에 devworld_lake 스키마가 있는지 확인
# ECS Exec으로 컨테이너 접속 후:
psql -h $DB_HOST -U $DB_USER -d airflow_db -c "\dn"
```

**해결:**
```bash
# 스키마가 없으면 생성
psql -h $DB_HOST -U $DB_USER -d airflow_db -c \
  "CREATE SCHEMA IF NOT EXISTS devworld_lake; GRANT ALL PRIVILEGES ON SCHEMA devworld_lake TO devworld;"
```

### 12-5. ECS Exec 실패

**증상**: `execute-command` 실행 시 `InvalidParameterException` 또는 `TargetNotConnectedException`

**해결:**

ECS Exec이 비활성화되어 있을 수 있습니다. 서비스에 enableExecuteCommand을 활성화합니다:

```bash
aws ecs update-service \
  --cluster devworld-cluster \
  --service devworld-api-server \
  --enable-execute-command \
  --force-new-deployment \
  --region ap-northeast-2
```

새 태스크가 시작된 후 다시 시도합니다. Session Manager 플러그인이 필요할 수 있습니다:

```bash
# macOS
brew install --cask session-manager-plugin
```

### 12-6. ALB 헬스체크 실패

**증상**: Target Health가 "unhealthy"

**진단:**
```bash
# 헬스체크 엔드포인트 확인 (컨테이너 내부에서)
curl -f http://localhost:8080/health
```

**자주 발생하는 원인:**
1. 컨테이너가 아직 시작 중 (startPeriod 60초 대기)
2. 포트 매핑 오류 - ECS Task Definition의 containerPort가 8080인지 확인
3. Security Group - ALB에서 ECS로 포트 8080 접근이 허용되어 있는지 확인

---

## 13. 롤백 방법

문제가 발생했을 때 이전 상태로 되돌리는 방법입니다.

### 13-1. ECS 서비스 롤백 (이전 Docker 이미지로 되돌리기)

```bash
# 1. ECR에서 이전 이미지 태그 확인
aws ecr list-images \
  --repository-name devworld/airflow \
  --region ap-northeast-2 \
  --query 'imageIds[*].imageTag' \
  --output table

# 2. 이전 태그로 Task Definition 업데이트
# terraform/ecs.tf에서 이미지 태그를 이전 버전으로 변경 후:
cd /Users/gimhojun/Desktop/devworld-airflow/terraform
terraform plan -out=tfplan
terraform apply tfplan

# 3. 또는 빠르게 이전 Task Definition 리비전으로 롤백
# 현재 Task Definition 리비전 확인
aws ecs describe-services \
  --cluster devworld-cluster \
  --services devworld-api-server \
  --region ap-northeast-2 \
  --query 'services[0].taskDefinition'

# 이전 리비전으로 서비스 업데이트 (예: revision 3 -> revision 2)
aws ecs update-service \
  --cluster devworld-cluster \
  --service devworld-api-server \
  --task-definition devworld-api-server:2 \
  --region ap-northeast-2

aws ecs update-service \
  --cluster devworld-cluster \
  --service devworld-scheduler \
  --task-definition devworld-scheduler:2 \
  --region ap-northeast-2
```

### 13-2. Terraform 롤백 (인프라 변경 되돌리기)

```bash
# S3에 저장된 이전 상태 파일 확인
aws s3api list-object-versions \
  --bucket devworld-terraform-state \
  --prefix airflow/terraform.tfstate \
  --query 'Versions[0:5].{VersionId:VersionId,LastModified:LastModified}' \
  --output table

# 특정 버전으로 상태 파일 다운로드
aws s3api get-object \
  --bucket devworld-terraform-state \
  --key airflow/terraform.tfstate \
  --version-id <PREVIOUS_VERSION_ID> \
  /tmp/terraform.tfstate.backup
```

> **주의**: Terraform 상태 파일 수동 복원은 위험합니다. 가능하면 `terraform plan` + `terraform apply`로 변경사항을 되돌리세요.

### 13-3. RDS 스냅샷 복원

```bash
# 1. 사용 가능한 스냅샷 목록 확인
aws rds describe-db-snapshots \
  --db-instance-identifier devworld-db \
  --region ap-northeast-2 \
  --query 'DBSnapshots[*].{Snapshot:DBSnapshotIdentifier,Created:SnapshotCreateTime,Status:Status}' \
  --output table

# 2. 스냅샷에서 새 인스턴스로 복원
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier devworld-db-restored \
  --db-snapshot-identifier <SNAPSHOT_ID> \
  --region ap-northeast-2
```

> **참고**: 복원된 인스턴스는 새 엔드포인트를 가집니다. Secrets Manager의 DB 접속 정보를 업데이트해야 합니다.

### 13-4. 전체 인프라 삭제 (최후 수단)

모든 AWS 리소스를 삭제하고 처음부터 다시 시작하는 경우:

```bash
cd /Users/gimhojun/Desktop/devworld-airflow/terraform

# 삭제 계획 확인
terraform plan -destroy

# 삭제 실행 (확인 프롬프트에서 "yes" 입력)
terraform destroy
```

> **경고**: 이 명령은 RDS 데이터를 포함한 모든 리소스를 삭제합니다. 반드시 RDS 스냅샷을 먼저 생성하세요.

```bash
# 삭제 전 RDS 스냅샷 생성
aws rds create-db-snapshot \
  --db-instance-identifier devworld-db \
  --db-snapshot-identifier devworld-db-backup-$(date +%Y%m%d) \
  --region ap-northeast-2
```

---

## 배포 완료 체크리스트

모든 단계를 완료했는지 확인합니다.

- [ ] **0단계**: AWS 계정, 도구 설치, 외부 서비스 준비
- [ ] **1단계**: AWS CLI, Terraform 설치, S3 백엔드 버킷 생성
- [ ] **2단계**: terraform.tfvars 파일 생성 및 값 입력
- [ ] **3단계**: terraform init/plan/apply 실행, 출력값 저장
- [ ] **4단계**: R2, GitHub, Ollama 시크릿 값 입력
- [ ] **5단계**: Docker 이미지 빌드, ECR 로그인, 이미지 푸시
- [ ] **6단계**: ECS 서비스 배포, Running 상태 확인, 헬스체크 통과
- [ ] **7단계**: app_db, platform_db 생성, 테이블 확인, DuckLake 스키마 생성
- [ ] **8단계**: Airflow UI 접속, 로그인, DAG 테스트 실행 성공
- [ ] **9단계**: ACM 인증서 ISSUED, DNS 레코드 추가, HTTPS 접속 확인
- [ ] **10단계**: GitHub Actions 워크플로우, OIDC Role, 자동 배포 테스트
- [ ] **11단계**: CloudWatch 알람 OK, SNS 이메일 구독 확인
