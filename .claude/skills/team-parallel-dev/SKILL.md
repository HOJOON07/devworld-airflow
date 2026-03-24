---
name: team-parallel-dev
description: Agent Teams로 새 데이터 소스/기능을 병렬 개발
disable-model-invocation: true
---

$ARGUMENTS 기능을 Agent Team으로 병렬 개발한다.

## 팀 구성 (5명)

| 팀원 | 역할 | 담당 |
|---|---|---|
| **Platform Lead** | 조율 | 태스크 분배, 인터페이스(스키마/시그니처) 합의, 진행 관리 |
| **Airflow Pipeline Engineer** | 구현 | DAG + dlt pipeline + 크롤러/파서/dedup 구현 |
| **Airflow Runtime Engineer** | 설정 | connection, variable, 스케줄, Airflow 설정 |
| **Infra Engineer** | 인프라 | Docker, Terraform, ECS 업데이트 |
| **QA Engineer** | 검증 | 테스트 작성 + DAG 로드 검증 + 통합 테스트 |

## 프로세스

1. **Platform Lead**가 작업을 분해하고 팀원에게 배정
2. 팀 전체가 데이터 스키마와 인터페이스를 합의
3. 각 팀원이 담당 영역을 병렬로 구현
4. **QA Engineer**가 통합 테스트로 전체 흐름 검증
5. **Platform Lead**가 결과를 종합

## 규칙
- 각 팀원은 자기 담당 영역만 수정 (충돌 방지)
- Raw First: 파싱 전에 raw 먼저 저장
- Thin DAG: DAG는 orchestration만
