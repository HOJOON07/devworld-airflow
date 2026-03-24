---
paths:
  - "terraform/**"
  - "Dockerfile"
  - "docker-compose.yml"
  - "docker-compose.*.yml"
  - ".github/workflows/**"
---

# 인프라 규칙

## 전체 배포 구조
- Frontend: Vercel (이 레포 밖)
- Backend API: ECS Fargate + ALB (이 레포 밖)
- Airflow: ECS Fargate (이 레포)

## Airflow ECS 배포
- airflow-webserver: ECS 서비스 1개
- airflow-scheduler: ECS 서비스 1개 (LocalExecutor로 태스크 직접 실행)
- worker/triggerer 서비스 없음, Redis 없음
- DAG 배포: Docker image에 포함 → ECR push → ECS redeploy

## 네트워크
- Private subnet: ECS tasks, RDS, 모든 내부 서비스
- Public subnet: ALB
- NAT Gateway 필요: 크롤러의 외부 웹사이트 접근 + R2 egress
- Airflow UI: ALB 레벨에서 IP 제한 또는 인증

## Terraform
- 인프라 변경은 Terraform으로 관리
- `terraform apply`는 Claude가 직접 실행하지 않는다 (plan까지만)
- 리소스: VPC, Subnets, NAT Gateway, Security Groups, ECS, ALB, RDS, ECR, IAM, Secrets Manager, CloudWatch

## Docker
- base image: apache/airflow 공식 이미지
- .env 파일에 시크릿 금지 — Secrets Manager 사용
- docker-compose는 로컬 개발용

## RDS PostgreSQL
- 초기: 단일 RDS 인스턴스, DB 분리 (app_db, airflow_db)
- 규모 커지면 인스턴스 분리 검토

## 시크릿
- DB credentials, R2 key, API key → AWS Secrets Manager
- Airflow connection/variable → Secrets Manager 백엔드 연동
- 코드에 자격증명 하드코딩 금지

## 모니터링
- ECS 서비스별 CloudWatch Log Group
- Airflow task 실패 알람
- RDS CPU/storage/connections 알람
- ECS task restart 알람
