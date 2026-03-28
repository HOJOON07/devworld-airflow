# 인프라/Docker/Terraform 리뷰

**리뷰어**: infra-reviewer
**리뷰 일자**: 2026-03-27
**수정 일자**: 2026-03-28

---

## 리뷰 결과

### Critical (3건) — 모두 해결됨

**C1. `.env` 파일에 실제 API 토큰이 커밋됨** ✅
- GITHUB_TOKEN, OLLAMA_API_KEY 평문 노출
- **해결**: `.env`는 `.gitignore`에 포함되어 Git에 커밋되지 않음 (01 리뷰 C-1에서 해결)

**C2. Airflow UI 인증 `admin/admin` 프로덕션 이미지 포함** ✅
- `config/simple_auth_manager_passwords.json`이 Dockerfile `COPY config/`로 이미지에 포함
- **해결**:
  - `.dockerignore` 생성하여 `config/simple_auth_manager_passwords.json` 제외
  - 추가로 `.env`, `*.pem`, `*.key`, `terraform/`, `tests/`, `docs/` 등도 제외
  - 프로덕션은 FAB Auth Manager 사용 예정 (`docs/auth-manager-guide.md` 참고)

**C3. ALB가 HTTP(80)만 지원 — HTTPS 미구성** ✅
- **해결**:
  - `terraform/variables.tf`에 `acm_certificate_arn` 변수 추가 (기본값 빈 문자열)
  - `terraform/alb.tf`에 HTTPS listener 추가 (`acm_certificate_arn` 설정 시에만 생성)
  - HTTP listener: ACM 설정 시 → HTTPS 리다이렉트, 미설정 시 → HTTP 직접 포워딩
  - `terraform/security_groups.tf`에 ALB 443 포트 인바운드 추가
  - 도메인 + ACM 인증서 발급 후 `acm_certificate_arn`만 설정하면 HTTPS 활성화

### Warning (12건) — 모두 해결됨

**W1: Fernet Key 빈 문자열** ✅
- **해결**: docker-compose에 Fernet key 설정 (01 리뷰 W-5에서 해결)

**W2: EXPOSE_CONFIG=True (airflow.env)** ✅
- **해결**: docker-compose에 `AIRFLOW__WEBSERVER__EXPOSE_CONFIG: 'false'` 명시 (01 리뷰 W-6에서 해결)

**W3: config/airflow.env 미사용** ✅
- **해결**: 유용한 설정을 docker-compose에 통합 후 파일 삭제 (01 리뷰 W-2에서 해결)

**W4: db migrate 동시 실행 race condition** ✅
- **해결**: scheduler에서 db migrate 제거, api-server healthy 대기 후 시작 (01 리뷰 W-3에서 해결)

**W5: entrypoint.sh 미사용** ✅
- **해결**: `scripts/entrypoint.sh` 삭제 (01 리뷰 W-1에서 해결)

**W6: ECS Task Definition에 R2/GITHUB_TOKEN/OLLAMA secrets 누락** ✅
- **해결**:
  - `terraform/secrets.tf`에 추가: `fernet_key`, `github_token`, `ollama_api_key`
  - `terraform/ecs.tf` api-server + scheduler 양쪽에 secrets 주입:
    - `AIRFLOW__CORE__FERNET_KEY`, `GITHUB_TOKEN`, `OLLAMA_API_KEY`
    - `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_ENDPOINT_URL` (R2)
  - `github_token`, `ollama_api_key`는 terraform apply 후 수동 설정:
    ```bash
    aws secretsmanager put-secret-value --secret-id devworld/github-token --secret-string "ghp_xxx"
    aws secretsmanager put-secret-value --secret-id devworld/ollama-api-key --secret-string "xxx"
    ```

**W7: STORAGE_RAW_BUCKET 환경변수 미정의** ✅
- **해결**: `.env`에 `RAW_BUCKET=devworld-raw` 명시 추가
  - `config.py`에서 `os.environ.get("RAW_BUCKET", "devworld-raw")`로 읽으므로 기본값으로 동작 중이었으나, 명시적 선언이 안전

**W8: RDS skip_final_snapshot = true** ✅
- **해결**: `terraform/rds.tf`에서 환경별 분기
  - `skip_final_snapshot = var.environment == "prod" ? false : true`
  - `final_snapshot_identifier` 추가
  - prod: 삭제 시 스냅샷 생성 / dev: 스냅샷 생략

**W9: RDS multi_az = false** ✅
- **해결**: W8과 함께 처리
  - `multi_az = var.environment == "prod" ? true : false`
  - prod: Multi-AZ (가용성) / dev: 단일 AZ (비용 절감)

**W10: CloudWatch 알람에 SNS 알림 없음** ✅
- **해결**:
  - `terraform/variables.tf`에 `alarm_email` 변수 추가 (기본값 빈 문자열)
  - `terraform/cloudwatch.tf`에 SNS topic + email subscription 추가 (`alarm_email` 설정 시에만 생성)
  - 모든 알람(RDS CPU, RDS Storage, ECS api-server, ECS scheduler)에 `alarm_actions`/`ok_actions` 연결
  - `alarm_email`만 설정하면 이메일 알림 활성화

**W11: requirements.txt에 dev/test 의존성 혼재** ✅
- **해결**:
  - `requirements.txt`: 프로덕션 패키지만 유지 (pytest, ruff, black 제거)
  - `requirements-dev.txt` 신규 생성: `-r requirements.txt` + dev/test 패키지
  - Dockerfile: `requirements.txt`만 설치 → 프로덕션 이미지에 불필요한 패키지 미포함
  - 로컬 개발: `pip install -r requirements-dev.txt`

**W12: Dockerfile base image 3.1.8 존재 여부** ✅
- **확인 완료**: `apache/airflow:3.1.8-python3.11`은 Docker Hub에 정상 존재
  - amd64 + arm64 멀티 아키텍처 지원
  - Airflow 3.1.8은 현재 최신 안정 버전 (3.2.x는 beta)

### Pass (9건)

- .gitignore 구성, docker-compose 서비스 구조, MinIO 초기화
- Terraform VPC/Subnet/NAT 구조, Secrets Manager, IAM 분리
- RDS 설정, Makefile, init-db.sql 스키마

---

## 기술 문서

### Docker 서비스 아키텍처
- postgres:15 (5433), minio (9000/9001), airflow-api-server (8080), airflow-scheduler
- 단일 Dockerfile, YAML anchor로 공통 설정 공유
- `.dockerignore`로 민감 파일 + 불필요 파일 제외

### Terraform 인프라 구조
- VPC 10.0.0.0/16, Public 2개 (ALB) + Private 2개 (ECS, RDS)
- ECS Fargate: api-server + scheduler (512 CPU / 1024 MiB)
- RDS PostgreSQL 15 (db.t3.micro, 20GB gp3, prod: Multi-AZ + final snapshot)
- ALB: HTTP(80) + HTTPS(443) (ACM 인증서 설정 시)
- ECR, Secrets Manager, CloudWatch + SNS 알림

### .env → Secrets Manager 전환 — 완료
- DB credentials, Airflow key: Terraform 정의 완료
- Fernet Key: `secrets.tf`에 추가 완료
- GITHUB_TOKEN, OLLAMA_API_KEY: `secrets.tf`에 추가 완료 (값은 수동 설정)
- R2 credentials: `secrets.tf`에 placeholder 존재 (값은 수동 설정)

### 프로덕션 배포 경로
- git push → Docker build → ECR push → ECS update-service
- CI/CD 파이프라인 미정의 (수동) — 추후 GitHub Actions 추가 검토
