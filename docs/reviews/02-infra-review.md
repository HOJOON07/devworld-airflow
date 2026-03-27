# 인프라/Docker/Terraform 리뷰

**리뷰어**: infra-reviewer
**리뷰 일자**: 2026-03-27

---

## 리뷰 결과

### Critical (3건)

**C1. `.env` 파일에 실제 API 토큰이 커밋됨**
- GITHUB_TOKEN, OLLAMA_API_KEY 평문 노출
- 수정: 즉시 revoke, `.env.example` 생성

**C2. Airflow UI 인증 `admin/admin` 프로덕션 이미지 포함**
- `config/simple_auth_manager_passwords.json`이 Dockerfile COPY됨
- 수정: 프로덕션 이미지 제외, Secrets Manager 주입

**C3. ALB가 HTTP(80)만 지원 — HTTPS 미구성**
- `terraform/alb.tf` — HTTPS listener, ACM 인증서 없음
- 수정: ACM + HTTPS(443) + HTTP→HTTPS 리다이렉트

### Warning (12건)

- W1: Fernet Key 빈 문자열
- W2: EXPOSE_CONFIG=True (airflow.env)
- W3: config/airflow.env 미사용
- W4: db migrate 동시 실행 race condition
- W5: entrypoint.sh 미사용
- W6: ECS Task Definition에 R2/GITHUB_TOKEN/OLLAMA secrets 누락
- W7: STORAGE_RAW_BUCKET 환경변수 미정의
- W8: RDS skip_final_snapshot = true
- W9: RDS multi_az = false
- W10: CloudWatch 알람에 SNS 알림 없음
- W11: requirements.txt에 dev/test 의존성 혼재
- W12: Dockerfile base image 3.1.8 존재 여부

### Pass (9건)

- .gitignore 구성, docker-compose 서비스 구조, MinIO 초기화
- Terraform VPC/Subnet/NAT 구조, Secrets Manager, IAM 분리
- RDS 설정, Makefile, init-db.sql 스키마

---

## 기술 문서

### Docker 서비스 아키텍처
- postgres:15 (5433), minio (9000/9001), airflow api-server (8080), scheduler
- 단일 Dockerfile, YAML anchor로 공통 설정 공유

### Terraform 인프라 구조
- VPC 10.0.0.0/16, Public 2개 (ALB) + Private 2개 (ECS, RDS)
- ECS Fargate: webserver + scheduler (512 CPU / 1024 MiB)
- RDS PostgreSQL 15 (db.t3.micro, 20GB gp3)
- ECR, Secrets Manager, CloudWatch

### 프로덕션 배포 경로
- git push → Docker build → ECR push → ECS update-service
- CI/CD 파이프라인 미정의 (수동)

### .env → Secrets Manager 전환
- DB credentials, Airflow key: Terraform 정의 완료
- GITHUB_TOKEN, OLLAMA_API_KEY, Fernet Key: 미정의 → 추가 필요
