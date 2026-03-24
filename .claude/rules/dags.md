---
paths:
  - "dags/**/*.py"
---

# Airflow DAG 규칙

- DAG 파일은 작게 유지한다
- 실제 로직은 재사용 가능한 Python 모듈로 이동
- `source`와 `partition_date` 기준으로 parameterize
- rerun / backfill을 전제로 작성
- 특정 source 하나만 가정한 구조를 피한다
- source-specific parsing rule을 DAG 내부에 하드코딩하지 않는다
- DAG는 orchestration만 담당하고, 비즈니스 로직을 구현하는 곳이 아니다
