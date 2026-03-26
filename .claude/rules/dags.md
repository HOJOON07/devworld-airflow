---
paths:
  - "dags/**/*.py"
---

# Airflow DAG 규칙

## Airflow 버전

- Airflow 3.x 사용
- `airflow.sdk` 모듈을 권장한다 (`from airflow.sdk import DAG, task` 등)
- `airflow.decorators`는 deprecated — 새 코드에서 사용하지 않는다

## DAG 체계

5개 DAG으로 구성한다:

| DAG | 역할 |
|---|---|
| `blog_crawl` | 개별 소스 크롤링 (스케줄 기반) |
| `blog_crawl_all` | 전체 소스 일괄 크롤링 |
| `dlt_load` | Bronze 적재 (dlt) |
| `dbt_transform` | Silver/Gold 변환 (Astronomer Cosmos) |
| `ai_enrich` | AI enrichment (LLM 기반) |

## 소스 관리

- `sources.yml` 파일로 크롤링 소스를 관리한다
- `sync_sources` 태스크로 sources.yml → DB 동기화

## 크롤링 동작

- DiscoveryService가 RSS feed에서 `content:encoded` 필드 존재 여부를 자동 판별한다
- `crawl_jobs` 테이블로 크롤링 작업을 추적한다

## dbt DAG 실행

- Astronomer Cosmos를 사용하여 dbt 프로젝트를 Airflow DAG으로 실행한다

## 일반 원칙

- DAG 파일은 작게 유지한다
- 실제 로직은 재사용 가능한 Python 모듈로 이동
- `source`와 `partition_date` 기준으로 parameterize
- rerun / backfill을 전제로 작성
- 특정 source 하나만 가정한 구조를 피한다
- source-specific parsing rule을 DAG 내부에 하드코딩하지 않는다
- DAG는 orchestration만 담당하고, 비즈니스 로직을 구현하는 곳이 아니다
