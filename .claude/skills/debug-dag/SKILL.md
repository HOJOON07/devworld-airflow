---
name: debug-dag
description: Airflow DAG 실행 오류 디버깅
disable-model-invocation: true
argument-hint: "<dag_name_or_path>"
allowed-tools: Read, Grep, Glob, Bash
---

$ARGUMENTS DAG의 오류를 진단한다.

## 진단 순서

1. DAG 파일 읽기 및 구문 확인
2. import 에러 체크
3. DAG 로드 테스트
4. 의존성 확인 (필요한 패키지, connection, variable)
5. 태스크 의존성 그래프 확인
6. 최근 변경 사항 확인 (git log)

## 진단 명령어

```
# import 에러 체크
python -c "import importlib; importlib.import_module('dags.$0')"

# DAG 로드 테스트
python -c "from airflow.models import DagBag; db=DagBag('.'); print(db.import_errors)"

# 린트 체크
ruff check dags/$0.py
```

## 출력 형식

- 원인 분석 (root cause)
- 수정 방안
- 관련 파일/라인 참조
