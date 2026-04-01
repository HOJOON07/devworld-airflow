# Remaining Issues Summary

**작성일**: 2026-03-29
**기준**: 01~08 리뷰 문서 + 당일 수정 반영

---

## Critical (미해결 2건)

| # | 출처 | 내용 | 영향 |
|---|---|---|---|
| C-4 | 02-infra | Terraform ECS Task Definition에 DuckLake/파이프라인 환경변수 대량 누락 | 프로덕션 ECS에서 모든 파이프라인 DAG 실패 |
| C-5 | 02-infra | IAM ecs_execution_secrets 정책에 secret ARN 3개 누락 | ECS 컨테이너 시작 실패 |

> C-4, C-5는 프로덕션 배포 시점에 해결. 로컬 개발 환경에서는 영향 없음.

## 해결 완료 (오늘)

| 항목 | 해결 내용 |
|---|---|
| github_enrich_service.py | 구현 완료 (enrich_github_prs, enrich_github_issues) |
| reverse_etl post_hook DDL | FTS를 별도 Airflow task로 분리 (create_fts_index) |
| Thin DAG 위반 | crawl_service.py 추출, DAG에서 호출만 |
| datetime.utcnow() | 전체 datetime.now(timezone.utc)로 전환 (0건) |
| enrich_service 중복 코드 | create_ducklake_connection import 사용 |
| DAG retry/timeout | DEFAULT_ARGS 추가 (8개 DAG 전부) |
| DAG on_failure_callback | common.py on_failure 콜백 추가 |
| reverse_etl ref() | hardcoded → {{ ref() }} 변경 |
| Prompt Injection | system/user role 분리 + ignore 가드 |
| f-string SQL injection | _esc() 헬퍼로 이스케이프 |
| dbt source freshness | loaded_at_field + freshness 설정 |
| GitHub Raw First | API JSON → MinIO 저장 추가 |
| load_service partition | partition_date WHERE 필터 + append |
| s3_use_ssl | 환경변수 분기 (config.use_ssl) |
| APP_DB_URL | .env에 추가 |
| DUCKLAKE_DATA_PATH 통일 | s3://devworld-lake로 통일 |
| 미사용 버킷 정리 | devworld-bronze, silver, gold-analytics 제거 |
| DuckLake 연결 문법 | ducklake:postgres: + libpq params로 통일 |

## Warning (미해결, 우선순위 순)

### P1 — 코드 품질

| # | 출처 | 내용 |
|---|---|---|
| W-5 | 04-dbt-dag | mart_articles.sql `now() as created_at` 비결정성 |
| W-3 | 04-dbt-dag | CLAUDE.md DAG 이름 불일치 (dbt_transform vs dbt_silver+dbt_gold) |

### P2 — 데이터 품질

| # | 출처 | 내용 |
|---|---|---|
| W-8 | 03-pipeline | Dedup 2단계만 구현 (설계 4단계) |
| W-4 | 04-dbt-dag | mart_source_stats 상관 서브쿼리 (성능) |

### P3 — 아키텍처 확장

| # | 출처 | 내용 |
|---|---|---|
| W-3 | 05-arch | Gold Analytics 레이어 미구현 |
| W-3 | 07-duckdb | DuckDB/DuckLake 버전 호환성 리스크 |
| W-4 | 05-arch | GitHub 파이프라인이 DuckLake Bronze를 거치지 않음 (PG 직접 저장) |

---

## 해결 현황 요약

- **전체 리뷰 항목**: Critical 14건 + Warning 40건 이상
- **해결**: Critical 12건, Warning 약 35건
- **미해결**: Critical 2건 (프로덕션 Terraform), Warning 7건
- **Best Practice 점수**: 5.5/10 → **7.0/10**
- **핵심 성과**: DuckLake 전환 완료, 블로그+GitHub 파이프라인 E2E 검증 완료, 설계-구현 괴리 해소
- **다음 우선순위**: 프로덕션 Terraform 정비 (C-4, C-5) → 배포 시점에 처리
