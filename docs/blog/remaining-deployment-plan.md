# 배포 마무리 계획: Airflow Execution API, 로그 설정, CI/CD

> 프로덕션 배포의 남은 작업들에 대한 구체적인 구현 계획입니다.
> 작성일: 2026-04-03

---

## 1. Scheduler Task에 api-server 사이드카 추가

### 문제

Airflow 3.x에서 scheduler가 태스크를 실행하려면 api-server의 **Execution API**에 접근해야 합니다:

```
AIRFLOW__CORE__EXECUTION_API_SERVER_URL = http://localhost:8080/execution/
```

현재 scheduler와 api-server가 **별도 ECS Service**라서 `localhost:8080`에 아무것도 없습니다. 태스크가 큐에 들어가자마자 실패합니다:

```
executor_state=failed, pid=None
```

### 해결

scheduler Task Definition에 api-server를 **세 번째 사이드카 컨테이너**로 추가합니다.

```
Scheduler Task (1 vCPU, 2GB 공유)
├── airflow-scheduler        ← 스케줄링 + 태스크 실행 (LocalExecutor)
├── airflow-dag-processor    ← DAG 파일 파싱
└── airflow-execution-api    ← Execution API 제공 (localhost:8080)
```

같은 Task 안의 컨테이너들은 **네트워크 네임스페이스를 공유**하므로 `localhost` 통신이 가능합니다.

### Terraform 변경

`ecs.tf`의 scheduler Task Definition `container_definitions`에 세 번째 컨테이너 추가:

```hcl
{
  name    = "airflow-execution-api"
  image   = "${aws_ecr_repository.airflow.repository_url}:latest"
  command = ["api-server"]

  portMappings = [
    {
      containerPort = 8080
      protocol      = "tcp"
    }
  ]

  # scheduler와 동일한 environment, secrets
  environment = [...]
  secrets     = [...]

  logConfiguration = {
    logDriver = "awslogs"
    options = {
      "awslogs-group"         = aws_cloudwatch_log_group.airflow.name
      "awslogs-region"        = var.aws_region
      "awslogs-stream-prefix" = "execution-api"
    }
  }
}
```

### 리소스 고려

3개 컨테이너가 1 vCPU / 2GB를 나눠 씁니다:
- scheduler: ~0.4 vCPU, ~800MB (LocalExecutor worker 포함)
- dag-processor: ~0.2 vCPU, ~400MB
- execution-api: ~0.2 vCPU, ~400MB (요청 처리만, 가벼움)

부족하면 2 vCPU / 4GB로 업그레이드.

### 기존 api-server Service는?

기존 독립 `devworld-api-server` ECS Service는 **Airflow UI(웹 대시보드) 전용**으로 유지합니다. ALB에서 `airflow.devworld.cloud` 요청을 받는 역할입니다.

```
airflow.devworld.cloud → ALB → devworld-api-server (UI 전용)
scheduler Task 내부 → localhost:8080 → execution-api (태스크 실행 전용)
```

### 실행 순서

```bash
# 1. Terraform 수정
vi terraform/ecs.tf  # scheduler container_definitions에 세 번째 컨테이너 추가

# 2. Terraform apply
cd terraform/
terraform plan -out=tfplan
terraform apply tfplan

# 3. ECS 재배포 (이미지는 같으므로 빌드 불필요)
aws ecs update-service --cluster devworld-cluster \
  --service devworld-scheduler --force-new-deployment \
  --region ap-northeast-2

# 4. 확인
aws ecs describe-services --cluster devworld-cluster \
  --services devworld-scheduler --region ap-northeast-2 \
  --query 'services[0].[serviceName,runningCount,deployments[0].rolloutState]' \
  --output text

# 5. DAG 실행 테스트
# Airflow UI에서 blog_crawl DAG 수동 트리거
```

### 검증

- blog_crawl DAG 수동 실행 → 태스크가 `running` 상태로 전환되는지
- scheduler 로그에 `pid=<숫자>`가 나오는지 (None이면 실패)
- CloudWatch에서 `execution-api` 스트림에 요청 로그가 찍히는지

---

## 2. Airflow 로그 설정 — 원격 로그 저장소

### 문제

```
Could not read served logs: Invalid URL 'http://:8793/log/...'
No host supplied
```

ECS Fargate에서 컨테이너의 hostname이 비어있어서, Airflow의 로컬 로그 서버(`http://<hostname>:8793`)가 동작하지 않습니다. 태스크가 실행되어도 UI에서 로그를 볼 수 없습니다.

### 해결

Airflow의 원격 로그 저장소를 **S3 호환 스토리지(Cloudflare R2)**로 설정합니다. 태스크 로그가 R2에 저장되고, UI에서 R2에서 직접 읽어옵니다.

### 환경변수 추가

ECS Task Definition의 scheduler, api-server 환경변수에 추가:

```
AIRFLOW__LOGGING__REMOTE_LOGGING=true
AIRFLOW__LOGGING__REMOTE_BASE_LOG_FOLDER=s3://devworld-raw/airflow-logs
AIRFLOW__LOGGING__REMOTE_LOG_CONN_ID=r2_conn
AIRFLOW__LOGGING__ENCRYPT_S3_LOGS=false
```

### Airflow Connection 설정

R2 접속을 위한 Airflow Connection을 환경변수로 설정:

```
AIRFLOW_CONN_R2_CONN=aws://<R2_ACCESS_KEY>:<R2_SECRET_KEY>@?endpoint_url=https://<ACCOUNT_ID>.r2.cloudflarestorage.com&region_name=auto
```

이걸 Secrets Manager에 저장하고 ECS secrets로 주입합니다.

### 실행 순서

```bash
# 1. Secrets Manager에 R2 Connection URL 저장
aws secretsmanager create-secret \
  --name devworld/airflow-r2-conn \
  --secret-string "aws://def4886707a65a327430d9d18ca69294:f339bb1130bed85abee5eba7958c72580e04abf27d113127907f8bfccd9a235f@?endpoint_url=https://47203eaf530c779845146dde86f189aa.r2.cloudflarestorage.com&region_name=auto" \
  --region ap-northeast-2

# 2. Terraform 수정
# - ECS environment에 REMOTE_LOGGING 환경변수 추가
# - ECS secrets에 AIRFLOW_CONN_R2_CONN 추가
# - IAM 정책에 새 시크릿 ARN 추가

# 3. Terraform apply + ECS 재배포

# 4. 확인
# Airflow UI에서 DAG 실행 후 로그 확인
```

### R2 버킷 구조

```
devworld-raw/
└── airflow-logs/
    └── dag_id=blog_crawl_all/
        └── run_id=scheduled__2026-04-03/
            └── task_id=sync_sources/
                └── attempt=1.log
```

### 검증

- DAG 실행 후 Airflow UI에서 로그가 보이는지
- R2 대시보드에서 `devworld-raw/airflow-logs/` 아래 파일이 생성되는지
- `http://:8793` 에러가 더 이상 안 나오는지

---

## 3. CI/CD — GitHub Actions 자동 배포

### 목표

```
개발자가 git push → GitHub Actions 자동 실행
  → Docker build (ARM64)
  → ECR push
  → ECS 재배포
  → 롤링 업데이트 (다운타임 없음)
```

### devworld 레포 (NestJS + Next.js)

#### `.github/workflows/deploy-api.yml`

```yaml
name: Deploy NestJS API

on:
  push:
    branches: [main]
    paths:
      - 'apps/api/**'
      - 'packages/**'

env:
  AWS_REGION: ap-northeast-2
  ECR_REPOSITORY: devworld-api
  ECS_CLUSTER: devworld-cluster
  ECS_SERVICE: devworld-nestjs-api

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/api/Dockerfile
          platforms: linux/arm64
          push: true
          tags: ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster ${{ env.ECS_CLUSTER }} \
            --service ${{ env.ECS_SERVICE }} \
            --force-new-deployment
```

#### 트리거 조건

- `apps/api/**` 변경 시에만 실행
- `packages/**` 변경도 포함 (공유 패키지가 API에 영향)
- `apps/web/**` 변경은 Vercel이 자동 처리

### devworld-airflow 레포 (Airflow)

#### `.github/workflows/deploy-airflow.yml`

```yaml
name: Deploy Airflow

on:
  push:
    branches: [main]
    paths-ignore:
      - 'docs/**'
      - 'terraform/**'
      - '*.md'

env:
  AWS_REGION: ap-northeast-2
  ECR_REPOSITORY: devworld-airflow
  ECS_CLUSTER: devworld-cluster

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/arm64
          push: true
          tags: ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy Airflow services
        run: |
          aws ecs update-service \
            --cluster ${{ env.ECS_CLUSTER }} \
            --service devworld-api-server \
            --force-new-deployment

          aws ecs update-service \
            --cluster ${{ env.ECS_CLUSTER }} \
            --service devworld-scheduler \
            --force-new-deployment
```

#### 트리거 조건

- `docs/**`, `terraform/**`, `*.md` 변경은 무시
- DAG, src, dbt, config, requirements.txt 변경 시 실행

### GitHub Secrets 설정

각 레포의 Settings → Secrets → Actions에 추가:

| Secret Name | 값 |
|------------|-----|
| `AWS_ACCESS_KEY_ID` | IAM 사용자의 Access Key |
| `AWS_SECRET_ACCESS_KEY` | IAM 사용자의 Secret Key |

> CI/CD 전용 IAM 사용자를 별도로 만들어서 최소 권한(ECR push + ECS update)만 부여하는 게 보안상 좋습니다.

### CI/CD 전용 IAM 정책

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices"
      ],
      "Resource": "arn:aws:ecs:ap-northeast-2:*:service/devworld-cluster/*"
    }
  ]
}
```

### 배포 흐름 정리

```
devworld 레포
├── apps/web/** 변경  → Vercel 자동 배포 (git push만)
├── apps/api/** 변경  → GitHub Actions
│   └── Docker build (ARM64) → ECR push → ECS update
└── docs, packages 변경 → 배포 안 함

devworld-airflow 레포
├── dags/, src/, dbt/, config/ 변경 → GitHub Actions
│   └── Docker build (ARM64) → ECR push → ECS update (api-server + scheduler)
├── terraform/ 변경 → 수동 terraform apply
└── docs/ 변경 → 배포 안 함
```

---

## 실행 순서 (내일)

### Step 1: Scheduler에 api-server 사이드카 추가 (30분)
1. `ecs.tf` 수정 — 세 번째 컨테이너 추가
2. `terraform apply`
3. ECS 재배포
4. blog_crawl DAG 수동 실행으로 검증

### Step 2: Airflow 로그 설정 (30분)
1. Secrets Manager에 R2 Connection 저장
2. `ecs.tf`에 로깅 환경변수 추가
3. IAM 정책 업데이트
4. `terraform apply` + ECS 재배포
5. DAG 실행 후 UI에서 로그 확인

### Step 3: CI/CD 설정 (30분)
1. CI/CD용 IAM 사용자 생성
2. GitHub Secrets 설정
3. `.github/workflows/` 파일 생성
4. 테스트 push로 자동 배포 확인

### Step 4: 전체 파이프라인 테스트 (1시간)
1. blog_crawl_all DAG 실행 — 크롤링 → R2 저장
2. dlt_load DAG 실행 — DuckLake Bronze 적재
3. dbt_silver, dbt_gold DAG 실행 — Silver/Gold 변환
4. Airflow UI에서 로그 확인
5. devworld.cloud에서 데이터 확인

---

## 체크리스트

- [ ] scheduler Task에 api-server 사이드카 추가
- [ ] blog_crawl DAG 수동 실행 성공
- [ ] Airflow 원격 로그 설정 (R2)
- [ ] Airflow UI에서 태스크 로그 확인
- [ ] GitHub Actions — NestJS 자동 배포
- [ ] GitHub Actions — Airflow 자동 배포
- [ ] CI/CD용 IAM 사용자 생성
- [ ] 전체 파이프라인 E2E 테스트
- [ ] Airflow Simple Auth Manager 비밀번호 고정
