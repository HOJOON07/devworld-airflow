---
name: dag-scaffold
description: 새 Airflow DAG + 테스트 보일러플레이트 생성
disable-model-invocation: true
argument-hint: "<dag_name>"
---

$ARGUMENTS 이름으로 새 DAG를 생성한다.

## 생성 파일

1. `dags/$0.py` — DAG 파일
2. `tests/test_$0.py` — 테스트 파일

## DAG 템플릿 규칙

- TaskFlow API (@task 데코레이터) 사용
- default_args 포함: owner, retries, retry_delay
- doc_md 작성
- tags 설정
- catchup=False
- source, partition_date 기준으로 parameterize
- 비즈니스 로직은 Python 모듈로 분리 (Thin DAG)
- rerun/backfill 전제로 작성

## 테스트 템플릿 규칙

- pytest 사용
- DAG 로드 테스트 필수 (import 에러 없이 로드되는지)
- 태스크 단위 테스트
- conftest.py에 공통 픽스처
