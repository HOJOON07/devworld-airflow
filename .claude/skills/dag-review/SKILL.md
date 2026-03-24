---
name: dag-review
description: 단일 Airflow DAG 코드 품질 리뷰
disable-model-invocation: true
argument-hint: "<dag_file_path>"
context: fork
agent: Explore
---

$ARGUMENTS DAG를 리뷰한다.

## 체크리스트

- [ ] TaskFlow API 사용 여부
- [ ] 하드코딩된 connection/variable 없음
- [ ] default_args 완전성 (owner, retries, retry_delay)
- [ ] catchup=False 설정
- [ ] source/partition_date parameterize
- [ ] Thin DAG: 비즈니스 로직이 Python 모듈로 분리되어 있는가
- [ ] 에러 핸들링 (on_failure_callback)
- [ ] 멱등성 보장 (같은 입력 → 같은 결과)
- [ ] Raw First: 파싱 전에 raw 저장하는가
- [ ] rerun/backfill 가능한 구조인가
- [ ] doc_md, tags 포함

## 출력 형식

- Pass / Warning / Critical 분류
- 파일:라인 참조
- 구체적 수정 방향
