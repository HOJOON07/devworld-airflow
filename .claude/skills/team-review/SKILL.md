---
name: team-review
description: Agent Teams로 다관점 코드/아키텍처 리뷰
disable-model-invocation: true
---

$ARGUMENTS에 대해 Agent Team으로 종합 리뷰한다.

## 팀 구성 (4명)

| 팀원 | 역할 | 리뷰 관점 |
|---|---|---|
| **Platform Lead** | 조율 | 리뷰 조율, 이슈 우선순위, 최종 판정 |
| **Code Reviewer** | 코드 품질 | 가독성, 패턴, 관심사 분리, 보안, 데이터 정합성 |
| **Architect** | 아키텍처 | 레이어 분리, 저장소 역할, 확장성, 원칙 준수 |
| **QA Engineer** | 테스트 | 테스트 커버리지, 재처리 검증, 엣지 케이스 |

## 프로세스

1. 각 팀원이 독립적으로 리뷰
2. 팀원 간 크로스 체크 (서로의 리뷰 검토)
3. **Platform Lead**가 종합 리포트 생성

## 출력 형식
- Critical / Warning / Pass 분류
- 파일:라인 참조
- 구체적 수정 방향 제시
