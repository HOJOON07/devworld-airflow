# Airflow 설정/운영 리뷰

**리뷰어**: airflow-reviewer
**리뷰 일자**: 2026-03-27
**수정 일자**: 2026-03-28

---

## 리뷰 결과

### Critical (3건) — 모두 해결됨

**C-1. `.env` 파일에 실제 API 토큰/시크릿이 하드코딩되어 Git에 노출 위험** ✅
- 파일: `.env:36-40`
- OLLAMA_API_KEY, GITHUB_TOKEN이 평문으로 존재
- **해결**: `.env`는 이미 `.gitignore`에 포함되어 Git에 커밋되지 않음. 노출 위험 없음

**C-2. `connections.json`에 자격증명이 평문으로 하드코딩** ✅
- 파일: `config/connections.json:7-8, 18-19, 27-28`
- MinIO, PostgreSQL, DuckLake 비밀번호 노출
- **해결**:
  - `connections.json` 삭제
  - `AIRFLOW_CONN_*` 환경변수 방식으로 전환 (`.env`에 `AIRFLOW_CONN_POSTGRES_APP`, `AIRFLOW_CONN_MINIO_DEFAULT` 추가)
  - `config/connections.json`을 `.gitignore`에 추가

**C-3. `simple_auth_manager_passwords.json`에 admin 비밀번호 평문** ✅
- 파일: `config/simple_auth_manager_passwords.json:1`
- `{"admin": "admin"}` 하드코딩
- **해결**:
  - `config/simple_auth_manager_passwords.json`을 `.gitignore`에 추가
  - Simple Auth Manager는 로컬 개발 전용, 프로덕션은 FAB Auth Manager로 전환 예정
  - 상세: `docs/auth-manager-guide.md` 참고

### Warning (8건) — 7건 해결, 1건 보류

**W-1: `entrypoint.sh`가 사용되지 않음 (Dead Code)** ✅
- **해결**: `scripts/entrypoint.sh` 삭제. docker-compose inline command로 충분

**W-2: `config/airflow.env`가 사용되지 않음 (parallelism 등 미적용)** ✅
- **해결**:
  - 유용한 설정을 docker-compose `environment`에 통합:
    - `AIRFLOW__CORE__PARALLELISM: 8`
    - `AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG: 4`
    - `AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG: 2`
    - `AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL: 30`
  - `config/airflow.env` 삭제

**W-3: `airflow db migrate`가 두 서비스에서 동시 실행 (Race Condition)** ✅
- **해결**:
  - scheduler에서 `airflow db migrate` 제거
  - scheduler가 `airflow-api-server: service_healthy` 조건으로 대기 후 시작
  - api-server에서만 db migrate 실행

**W-4: 서비스 이름 `airflow-webserver` vs 실제 `api-server` 불일치** ✅
- **해결**: `airflow-api-server`로 전체 통일
  - `docker-compose.yml`: 서비스명 + EXECUTION_API_SERVER_URL
  - `terraform/ecs.tf`: task definition, service, container name
  - `terraform/variables.tf`: `api_server_cpu`, `api_server_memory`
  - `terraform/cloudwatch.tf`: alarm 리소스명
  - `terraform/alb.tf`: target group 이름
  - `terraform/security_groups.tf`: description
  - `terraform/secrets.tf`: description
  - `terraform/terraform.tfvars.example`: 변수명
  - `HARNESS_DESIGN.md`, `docs/auth-manager-guide.md`

**W-5: `AIRFLOW__CORE__FERNET_KEY`가 빈 문자열** ✅
- **해결**: `base64(32바이트 랜덤)` 키 생성하여 docker-compose에 설정
  - Fernet Key: Airflow가 DB에 저장하는 Connection 비밀번호, Variable 등을 AES 암호화하는 키
  - 프로덕션에서는 Secrets Manager에 저장하여 ECS 환경변수로 주입

**W-6: `EXPOSE_CONFIG=True` (보안 위험, 현재 미적용)** ✅
- **해결**:
  - docker-compose에 `AIRFLOW__WEBSERVER__EXPOSE_CONFIG: 'false'` 명시 추가
  - `config/airflow.env` 삭제 (W-2에서 함께 처리)
  - EXPOSE_CONFIG=True는 Airflow UI에서 전체 설정값(DB 비밀번호, API 키 등)이 노출되는 보안 위험

**W-7: `variables.json`에 DuckLake catalog URL이 자격증명 포함** 🔄
- **보류**: DuckDB/DuckLake 리뷰(07)에서 함께 처리 예정

**W-8: `entrypoint.sh`의 user 생성 로직이 Airflow 3.x Simple Auth Manager와 충돌** ✅
- **해결**: W-1에서 `entrypoint.sh` 삭제로 함께 해결

### Pass (7건)

- LocalExecutor 설정, PostgreSQL 구성, MinIO 구성, Dockerfile 구조
- Volume 마운트, `.gitignore`, Variable 구조

---

## 기술 문서

### 서비스 구조

| 서비스 | 역할 | 포트 |
|---|---|---|
| postgres | Airflow 메타 + app_db + DuckLake catalog | 5433:5432 |
| minio | 로컬 S3 호환 스토리지 | 9000, 9001 |
| minio-init | 버킷 자동 생성 (one-shot) | - |
| airflow-api-server | Airflow API Server (db migrate + api-server) | 8080 |
| airflow-scheduler | DAG 스케줄링 + LocalExecutor (api-server healthy 후 시작) | - |

### 인증 방식
- 로컬: Simple Auth Manager (`simple_auth_manager_passwords.json`)
- 프로덕션: FAB Auth Manager (`apache-airflow-providers-fab`)
- 상세: `docs/auth-manager-guide.md`

### 개선 권고 (우선순위별)

1. ~~시크릿 관리 정비~~ → 해결됨
2. ~~entrypoint.sh 활용 또는 제거~~ → 삭제됨
3. ~~db migrate race condition 해결~~ → scheduler에서 제거됨
4. ~~Fernet Key 설정~~ → 설정됨
5. 프로덕션 Secrets Manager 전환 → Terraform 배포 시 적용 예정
