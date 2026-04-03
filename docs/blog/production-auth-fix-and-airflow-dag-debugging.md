# 프로덕션 Auth 버그 수정 + Airflow DAG 디버깅 실전기

> GitHub OAuth 인증 버그로 다른 사람이 내 계정으로 로그인되는 치명적 문제 해결, 그리고 Airflow 3.x Execution API JWT 인증 + R2 region 설정까지 — 프로덕션에서 만난 버그들의 원인과 해결 과정을 기록합니다.
> 작성일: 2026-04-03

---

## 목차

1. [CRITICAL: 다른 사람이 내 계정으로 로그인되는 버그](#1-critical-다른-사람이-내-계정으로-로그인되는-버그)
2. [Private Subnet RDS 접근 — Bastion EC2 + SSH 터널](#2-private-subnet-rds-접근--bastion-ec2--ssh-터널)
3. [Airflow 3.x Execution API JWT 인증 실패](#3-airflow-3x-execution-api-jwt-인증-실패)
4. [dbt Silver 모델 실패 — R2 region 설정 누락](#4-dbt-silver-모델-실패--r2-region-설정-누락)
5. [Airflow Remote Logging 삽질](#5-airflow-remote-logging-삽질)
6. [ECS Exec으로 컨테이너 디버깅](#6-ecs-exec으로-컨테이너-디버깅)
7. [최종 결과 & 배운 점](#7-최종-결과--배운-점)

---

## 1. CRITICAL: 다른 사람이 내 계정으로 로그인되는 버그

### 증상

프로덕션(devworld.cloud)에서 다른 사람이 GitHub 로그인을 했는데, **내 프로필과 내가 쓴 아티클**이 보인다는 제보가 들어왔습니다.

### 원인 분석

GitHub OAuth에서 이메일을 가져올 수 없는 경우(비공개 설정)가 있습니다. 기존 코드는 이 경우 빈 문자열(`""`)을 저장했고, 사용자 식별을 `findByEmail`로 하고 있었습니다.

```typescript
// 문제의 코드 — email 기반 사용자 식별
let user = await this.usersService.findByEmail(primaryEmail);
```

두 번째 사용자가 GitHub 로그인 → email 비공개 → `findByEmail("")` → **첫 번째 사용자의 빈 이메일과 매칭** → 같은 계정으로 로그인되는 상황이었습니다.

### 해결

GitHub OAuth만 사용하는 플랫폼이므로, 사용자 식별을 `provider + providerId`(GitHub ID) 기준으로 변경했습니다.

**1단계: 코드 수정**

```typescript
// github.strategy.ts — providerId 기반 식별로 변경
let user = await this.usersService.findByProviderId(id, AuthProvider.GITHUB);

if (!user) {
  user = await this.usersService.create({
    email: primaryEmail,  // null 허용
    name: displayName || null,
    avatar: photos?.[0]?.value || null,
    provider: AuthProvider.GITHUB,
    providerId: id,
  });
}
```

```typescript
// user.entity.ts — email nullable로 변경
@Column({ unique: true, nullable: true })
@Index()
email: string | null;
```

**2단계: DB 마이그레이션**

```sql
ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
UPDATE users SET email = NULL WHERE email = '';
```

### 왜 계정 삭제가 필요 없었나?

Article 엔티티에 `onDelete: 'SET NULL'` 설정이라 유저 삭제 시 글의 `authorId`가 NULL로 바뀔 뿐이었지만, 기존 계정의 `providerId`가 이미 설정되어 있었기 때문에 삭제 없이 DB 스키마 변경만으로 해결됐습니다.

---

## 2. Private Subnet RDS 접근 — Bastion EC2 + SSH 터널

### 문제

RDS가 Private Subnet에 있어서 로컬에서 직접 접속이 불가능합니다. DB 마이그레이션을 실행할 방법이 필요했습니다.

### 해결: Terraform으로 임시 Bastion 생성

```hcl
# bastion.tf — 임시 파일, 작업 후 삭제
resource "aws_instance" "bastion" {
  ami                         = data.aws_ami.amazon_linux.id
  instance_type               = "t4g.micro"  # t4g.nano는 프리티어 대상 아님!
  key_name                    = aws_key_pair.bastion.key_name
  subnet_id                   = aws_subnet.public[0].id
  vpc_security_group_ids      = [aws_security_group.bastion.id]
  associate_public_ip_address = true
}
```

> **주의**: `t4g.nano`는 Free Tier 대상이 아닙니다. `t4g.micro`를 사용해야 합니다.

### SSH 터널 + psql 접속

```bash
# 로컬 5432는 PostgreSQL이 사용 중이므로 15432로 포워딩
ssh -i ~/.ssh/devworld-bastion -L 15432:<RDS_ENDPOINT>:5432 ec2-user@<BASTION_IP> -N

# 다른 터미널에서
psql -h localhost -p 15432 -U devworld -d platform_db
```

### 삽질: DB 이름 찾기

NestJS 앱의 users 테이블이 `app_db`가 아닌 `platform_db`에 있었습니다. `\dt` 명령으로 테이블 목록 확인하는 게 필수입니다.

### 비밀번호 확인

Terraform의 `random_password`로 생성된 비밀번호는 state에서 확인:

```bash
terraform state pull | python3 -c "import sys,json; state=json.load(sys.stdin); [print(i['attributes']['result']) for r in state['resources'] if r['type']=='random_password' for i in r['instances']]"
```

### 정리

작업 완료 후 `bastion.tf` 삭제 → `terraform apply`로 리소스 정리.

---

## 3. Airflow 3.x Execution API JWT 인증 실패

### 증상

DAG 트리거 시 모든 task가 "재시도 대기중"으로 실패:

```
airflow.sdk.api.client.ServerResponseError: Invalid auth token: Signature verification failed
```

### 원인

Airflow 3.x에서는 Execution API JWT 인증에 `AIRFLOW__WEBSERVER__SECRET_KEY`가 아닌 **`AIRFLOW__API_AUTH__JWT_SECRET`**을 사용합니다. 이 값을 설정하지 않으면 **각 컨테이너가 랜덤 키를 각자 생성**해서 서명이 불일치합니다.

### Airflow 3.x 시크릿 키 정리

| 환경변수 | 용도 | Execution API 관련? |
|---------|------|------------------|
| `AIRFLOW__WEBSERVER__SECRET_KEY` | Flask 세션 (3.x deprecated) | ❌ |
| `AIRFLOW__API__SECRET_KEY` | CSRF, Celery worker 인증 | ❌ |
| **`AIRFLOW__API_AUTH__JWT_SECRET`** | **Execution API JWT 서명/검증** | **✅ 이게 필요** |
| `AIRFLOW__CORE__FERNET_KEY` | Connection 암호화 | ❌ |

### 해결

```hcl
# secrets.tf — JWT 시크릿 추가
resource "random_password" "airflow_jwt_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret_version" "airflow_jwt_secret" {
  secret_id     = aws_secretsmanager_secret.airflow_jwt_secret.id
  secret_string = random_password.airflow_jwt_secret.result
}
```

**4개 Airflow 컨테이너 모두**에 동일한 시크릿을 주입:

```hcl
# ecs.tf — api-server, scheduler, dag-processor, execution-api 모두
{
  name      = "AIRFLOW__API_AUTH__JWT_SECRET"
  valueFrom = "${aws_secretsmanager_secret.airflow_jwt_secret.arn}"
},
```

IAM execution role에 새 시크릿 접근 권한 추가도 필수입니다.

> **참고**: [GitHub Issue #59373](https://github.com/apache/airflow/issues/59373), [#62026](https://github.com/apache/airflow/issues/62026)에서 동일 문제가 보고되었습니다.

---

## 4. dbt Silver 모델 실패 — R2 region 설정 누락

### 증상

`stg_articles` (VIEW) → 성공, `int_articles_cleaned` (TABLE) → 실패. scheduler 로그에서는 `exit_code=1`만 보이고 dbt 에러 메시지는 확인 불가.

### 디버깅 과정

task 로그를 볼 수 없어서 **ECS Exec**으로 컨테이너에 직접 진입해 dbt를 수동 실행했습니다:

```bash
export HOME=/home/airflow && cd /opt/airflow
/home/airflow/.local/bin/dbt run --select int_articles_cleaned \
  --profiles-dir dbt --project-dir dbt 2>&1
```

### 에러 메시지

```
HTTP Error: HTTP GET error reading '...devworld-lake/bronze/articles/...'
  in region 'ap-northeast-2' (HTTP 400 Bad Request)

InvalidRegionName: The region name 'ap-northeast-2' is not valid.
  Must be one of: wnam, enam, weur, eeur, apac, oc, auto
```

### 원인

**Cloudflare R2는 AWS region이 아닌 자체 region 체계를 사용합니다.** DuckDB가 AWS 기본 region(`ap-northeast-2`)을 사용하면서 R2가 거부한 것입니다.

### 영향받은 파일들

전체 코드베이스를 검색하여 R2 region 설정이 필요한 **모든 곳**을 수정했습니다:

| 파일 | 수정 내용 |
|------|---------|
| `dbt/profiles.yml` | `s3_region: auto` 추가 |
| `src/infrastructure/ducklake/setup.py` | `SET s3_region` 추가 |
| `src/shared/config.py` | 기본값 `us-east-1` → `auto` |
| `src/infrastructure/storage/s3_storage.py` | boto3에 `region_name` 추가 |

### dbt profiles.yml 수정

```yaml
settings:
  s3_region: "{{ env_var('STORAGE_REGION', 'auto') }}"  # 추가!
  s3_endpoint: "{{ env_var('STORAGE_ENDPOINT_URL', '...') | replace('https://', '') }}"
  s3_access_key_id: "{{ env_var('STORAGE_ACCESS_KEY', '...') }}"
  s3_secret_access_key: "{{ env_var('STORAGE_SECRET_KEY', '...') }}"
  s3_url_style: path
  s3_use_ssl: "{{ env_var('S3_USE_SSL', 'false') }}"
```

### DuckLake setup.py 수정

```python
# s3_region 설정 추가
conn.execute(f"SET s3_region='{_esc(storage.region)}'")
conn.execute(f"SET s3_endpoint='{_esc(endpoint)}'")
# ... 나머지 S3 설정
```

### 왜 VIEW는 성공하고 TABLE만 실패했나?

- `stg_articles`는 `+materialized: view` — SQL 정의만 생성, 실제 R2 접근 없음
- `int_articles_cleaned`는 `+materialized: table` — R2에서 Parquet 읽기 + 쓰기 필요

VIEW는 데이터를 읽지 않으므로 region 에러가 발생하지 않았습니다.

---

## 5. Airflow Remote Logging 삽질

### 시도

Airflow UI에서 task 로그를 보기 위해 CloudWatch remote logging을 설정했습니다:

```
AIRFLOW__LOGGING__REMOTE_LOGGING=true
AIRFLOW__LOGGING__REMOTE_BASE_LOG_FOLDER=cloudwatch:///airflow/devworld/task-logs
AIRFLOW__LOGGING__REMOTE_LOG_CONN_ID=aws_default
AIRFLOW_CONN_AWS_DEFAULT=aws://
```

### 결과: Airflow 부팅 크래시

```
ImportError: Unable to load logging config from
airflow.config_templates.airflow_local_settings.DEFAULT_LOGGING_CONFIG
due to: IndexError: list index out of range
```

모든 컨테이너가 `exit_code=1`로 크래시 루프에 빠졌습니다. **즉시 롤백**했습니다.

### 교훈

- Airflow 3.x에서 `cloudwatch://` remote logging URI가 그대로 동작하지 않을 수 있음
- logging 설정 변경은 Airflow 부팅 자체를 막을 수 있어 위험도가 높음
- 크래시 시 원인 파악이 어려워짐 (로그 자체가 안 남음)
- **remote logging은 로컬에서 먼저 테스트 후 프로덕션 적용** 필요

---

## 6. ECS Exec으로 컨테이너 디버깅

dbt 에러를 CloudWatch 로그에서 볼 수 없어서, ECS Exec으로 컨테이너에 직접 진입하는 방법을 사용했습니다.

### 설정 과정

**1단계: ECS Exec 활성화**

```bash
aws ecs update-service --cluster devworld-cluster \
  --service devworld-scheduler \
  --enable-execute-command --force-new-deployment
```

> 활성화 후 **재배포된 task에서만** 동작합니다. 기존 task는 안 됩니다.

**2단계: IAM Task Role에 SSM 권한 추가**

```hcl
resource "aws_iam_policy" "ecs_task_ssm" {
  policy = jsonencode({
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel",
      ]
      Resource = "*"
    }]
  })
}
```

> 이 권한이 없으면 `TargetNotConnectedException` 에러가 발생합니다.

**3단계: 접속**

```bash
TASK_ARN=$(aws ecs list-tasks --cluster devworld-cluster \
  --service-name devworld-scheduler \
  --query 'taskArns[0]' --output text)

aws ecs execute-command --cluster devworld-cluster \
  --task $TASK_ARN --container airflow-scheduler \
  --interactive --command "/bin/bash"
```

### 주의: 환경변수

ECS Exec으로 접속하면 **root** 사용자입니다. `su - airflow`로 전환하면 `-` 플래그가 환경변수를 리셋해서 ECS 환경변수가 사라집니다.

```bash
# ❌ 환경변수가 사라짐
su - airflow -c "dbt run ..."

# ✅ root에서 직접 실행 (환경변수 유지)
export HOME=/home/airflow && dbt run ...
```

---

## 7. 최종 결과 & 배운 점

### 해결한 문제들

| 문제 | 원인 | 해결 |
|------|------|------|
| 다른 사람이 내 계정으로 로그인 | `findByEmail("")` 매칭 | `findByProviderId` 기반으로 변경 |
| DAG task 전부 실패 | `AIRFLOW__API_AUTH__JWT_SECRET` 누락 | 모든 컨테이너에 동일 시크릿 주입 |
| dbt TABLE 모델 실패 | R2에 `ap-northeast-2` region 전달 | `s3_region: auto` 설정 |
| Airflow 부팅 크래시 | CloudWatch remote logging URI 호환성 | 설정 롤백 |
| ECS Exec 접속 불가 | SSM 권한 누락 | IAM Task Role에 ssmmessages 권한 추가 |

### DAG 실행 현황

| DAG | 상태 |
|-----|------|
| blog_crawl_all | ✅ 성공 (24개 소스 크롤링) |
| dbt_silver | ✅ 성공 |
| ai_enrich | ✅ 성공 |
| github_ai_enrich | ✅ 성공 (68초) |

### 배운 점

1. **Airflow 3.x는 2.x와 많이 다르다**: Execution API, api-server(webserver 대체), dag-processor 분리, JWT 인증 등 변경 사항이 많습니다. 공식 마이그레이션 가이드와 GitHub Issues를 꼭 확인하세요.

2. **Cloudflare R2 ≠ AWS S3**: R2는 region 체계가 다릅니다(`auto`, `wnam`, `enam` 등). DuckDB, boto3, dlt 등 S3 호환 도구마다 region 설정을 확인해야 합니다.

3. **ECS에서 로그 접근은 미리 준비해야 한다**: LocalExecutor + Airflow 3.x supervisor 조합에서는 task stdout이 CloudWatch에 남지 않습니다. Remote logging 또는 ECS Exec을 미리 설정해두세요.

4. **Bastion은 Terraform으로 관리하면 편하다**: 임시 bastion을 `.tf` 파일로 만들고, 작업 후 삭제 → `terraform apply`로 깔끔하게 정리할 수 있습니다.

5. **프로덕션 인증 로직은 edge case를 항상 고려해야 한다**: GitHub OAuth에서 email이 비공개인 경우, email이 null인 경우 등을 처리하지 않으면 심각한 보안 문제가 됩니다.

---

### 남은 과제

- [ ] Airflow Simple Auth Manager — 재시작마다 비밀번호 변경 문제
- [ ] Remote logging 정상 설정 (CloudWatch or S3)
- [ ] GitHub DAG 전체 파이프라인 테스트 (collect → enrich → gold)
- [ ] CI/CD — GitHub Actions로 자동 배포
- [ ] blog_crawl_all 성능 최적화 (현재 2 vCPU / 4 GB)
