---
name: team-research
description: Agent Teams로 기술 리서치/아키텍처 결정을 병렬 수행
disable-model-invocation: true
---

$ARGUMENTS에 대해 Agent Team으로 리서치한다.

## 팀 구성 (4명)

| 팀원 | 역할 | 조사 관점 |
|---|---|---|
| **Platform Lead** | 조율 | 토론 진행, 결론 종합, 의사결정 |
| **Architect** | 설계 | 아키텍처 패턴, 확장성, DuckLake/R2 활용, 트레이드오프 |
| **Airflow Runtime Engineer** | 운영 | Airflow 운영 관점 실현 가능성, 스케줄/실행 영향 |
| **Infra Engineer** | 인프라 | 인프라 비용, 복잡도, AWS 서비스 선택, Terraform 영향 |

## 프로세스

1. 각 팀원이 자기 관점에서 독립 조사
2. 팀원 간 상호 토론 (장단점 반박/검증)
3. **Platform Lead**가 합의된 권고안을 종합

## 출력 형식
- 권고안 (1개)
- 근거 및 트레이드오프
- 대안과 기각 사유
