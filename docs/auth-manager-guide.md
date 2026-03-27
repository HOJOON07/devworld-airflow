# Airflow Auth Manager 가이드

## 개요

Airflow 3.x는 Auth Manager 플러그인 시스템으로 인증/인가를 관리한다.
환경변수 `AIRFLOW__CORE__AUTH_MANAGER`로 어떤 Auth Manager를 쓸지 결정하며,
로컬과 프로덕션에서 같은 Docker 이미지를 쓰되 환경변수만 다르게 설정한다.

---

## 환경별 Auth Manager

| 환경 | Auth Manager | 설정 방식 |
|---|---|---|
| 로컬 개발 | Simple Auth Manager (기본값) | `.env` + `simple_auth_manager_passwords.json` |
| 프로덕션 | FAB Auth Manager | ECS Task Definition 환경변수 |

---

## 로컬 개발 (Simple Auth Manager)

Airflow 3.x 기본 Auth Manager. 개발/테스트 전용.

### 설정

```bash
# docker-compose.yml (현재 설정)
AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE: /opt/airflow/config/simple_auth_manager_passwords.json
```

### 유저 관리

```bash
# docker-compose.yml environment 또는 .env
AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS="admin:admin,viewer:viewer"
```

### 패스워드

- `config/simple_auth_manager_passwords.json`에 저장 (`.gitignore` 대상)
- 파일이 없으면 자동 생성되어 webserver 로그에 출력됨
- 수동 수정 가능: `{"admin": "원하는_비밀번호"}`

### 역할 체계

| Role | 권한 |
|---|---|
| viewer | DAG/asset/pool 읽기 전용 |
| user | viewer + DAG 편집/생성/삭제 |
| op | user + pool/asset/config/connection/variable 전체 제어 |
| admin | 모든 권한 |

### 인증 비활성화 (선택)

```bash
AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS=True
```

모든 사용자가 인증 없이 admin으로 접근. 로컬 개발 시 편의용.

---

## 프로덕션 (FAB Auth Manager)

Flask AppBuilder 기반. DB에 유저/역할 저장, OAuth2/LDAP 지원.

### 전제 조건

`requirements.txt`에 이미 포함:
```
apache-airflow-providers-fab>=2.0.0
```

### Step 1: Secrets Manager에 FAB Secret Key 추가

```hcl
# terraform/secrets.tf

resource "aws_secretsmanager_secret" "airflow_fab_secret" {
  name        = "${var.project_name}/airflow-fab-secret"
  description = "FAB Auth Manager secret key"

  tags = {
    Name = "${var.project_name}-airflow-fab-secret"
  }
}

resource "aws_secretsmanager_secret_version" "airflow_fab_secret" {
  secret_id     = aws_secretsmanager_secret.airflow_fab_secret.id
  secret_string = random_password.fab_secret.result
}

resource "random_password" "fab_secret" {
  length  = 64
  special = false
}
```

### Step 2: ECS Task Definition 환경변수 추가

```hcl
# terraform/ecs.tf — webserver task definition

environment = [
  { name = "AIRFLOW__CORE__EXECUTOR", value = "LocalExecutor" },
  { name = "AIRFLOW__CORE__LOAD_EXAMPLES", value = "false" },
  # FAB Auth Manager 활성화
  {
    name  = "AIRFLOW__CORE__AUTH_MANAGER"
    value = "airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager"
  },
]

secrets = [
  {
    name      = "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"
    valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:connection_string::"
  },
  {
    name      = "AIRFLOW__WEBSERVER__SECRET_KEY"
    valueFrom = "${aws_secretsmanager_secret.airflow_secret_key.arn}"
  },
  # FAB secret key
  {
    name      = "AIRFLOW__FAB__SECRET_KEY"
    valueFrom = "${aws_secretsmanager_secret.airflow_fab_secret.arn}"
  },
]
```

scheduler task definition에도 동일하게 `AIRFLOW__CORE__AUTH_MANAGER` 추가.

### Step 3: 초기 Admin 유저 생성 (1회성)

배포 후 ECS Exec으로 컨테이너에 접근:

```bash
aws ecs execute-command \
  --cluster devworld-cluster \
  --task <task-id> \
  --container airflow-api-server \
  --interactive \
  --command "/bin/bash"
```

컨테이너 안에서 admin 유저 생성:

```bash
airflow users create \
  --username admin \
  --password <강한_패스워드> \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@devworld.com
```

유저 정보는 RDS PostgreSQL에 저장되므로 컨테이너 재시작과 무관하게 유지된다.

### Step 4: 추가 유저 관리

생성 후에는 Airflow 웹 UI(Security → List Users)에서 유저 추가/수정/삭제 가능.

CLI로도 가능:

```bash
# 유저 목록
airflow users list

# 유저 삭제
airflow users delete --username <username>
```

---

## 동작 원리

```
┌─────────────────────────────────────────────────┐
│ 같은 Docker 이미지                                │
│ (apache-airflow-providers-fab 포함)               │
├─────────────────────────────────────────────────┤
│                                                   │
│  로컬 (.env)                                      │
│  → AUTH_MANAGER 미설정 → Simple Auth Manager       │
│  → passwords.json 파일 기반 인증                   │
│                                                   │
│  프로덕션 (ECS Task Definition)                    │
│  → AUTH_MANAGER = FabAuthManager                  │
│  → FAB_SECRET_KEY = Secrets Manager               │
│  → DB_CONN = RDS (Secrets Manager)                │
│  → airflow db migrate 시 FAB 테이블 자동 생성       │
│                                                   │
└─────────────────────────────────────────────────┘
```

코드 변경 없이 Terraform 환경변수 설정만으로 인증 방식이 전환된다.

---

## 사용 가능한 Auth Manager 목록 (참고)

| Auth Manager | 패키지 | 상태 | 용도 |
|---|---|---|---|
| Simple | airflow 내장 | stable | 개발/테스트 |
| FAB | apache-airflow-providers-fab | stable | 범용 프로덕션 |
| AWS | apache-airflow-providers-amazon | alpha | AWS 네이티브 (IAM Identity Center) |
| Keycloak | apache-airflow-providers-keycloak | stable | Keycloak SSO 통합 |

AWS Auth Manager는 IAM Identity Center + Amazon Verified Permissions 기반이나,
현재 alpha 상태이므로 FAB을 권장한다. 안정화 후 전환 검토.

---

## 관련 파일

| 파일 | 역할 |
|---|---|
| `requirements.txt` | `apache-airflow-providers-fab>=2.0.0` 포함 |
| `config/simple_auth_manager_passwords.json` | 로컬 패스워드 (`.gitignore` 대상) |
| `docker-compose.yml` | 로컬 Simple Auth Manager 설정 |
| `terraform/ecs.tf` | 프로덕션 FAB 환경변수 |
| `terraform/secrets.tf` | FAB secret key (Secrets Manager) |
