---
name: github-enrich
description: GitHub PR/Issue AI enrichment 가이드
disable-model-invocation: true
---

GitHub PR/Issue에 대한 AI enrichment 코드를 작성한다.

## PR enrichment

### 입력
- github_prs 테이블 (title, body, state, labels)
- github_pr_files 테이블 (상위 10개 파일의 patch)

### AI 산출물 (github_pr_ai_summaries)
- ai_summary: PR 상세 요약
- key_changes: 핵심 변경 목록 (JSONB array)
- impact_analysis: 영향 분석 + 위험도
- change_type: feature/bugfix/refactor/docs/test
- ai_code_review: 코드 품질, 패턴, 개선점

## Issue enrichment

### 입력
- github_issues 테이블 (title, body, state, labels)

### AI 산출물 (github_issue_ai_summaries)
- ai_summary: 이슈 요약
- key_points: 핵심 포인트 목록 (JSONB array)
- suggested_solution: 제안 솔루션
- contribution_difficulty: beginner/intermediate/advanced

## 공통
- Ollama Cloud API 사용 (기존 ollama_client.py 재사용)
- 이미 enrichment된 PR/Issue는 스킵
- PR diff는 상위 10개 파일 patch만 LLM에 전달 (토큰 절약)

## 하지 말 것
- 전체 diff를 LLM에 보내지 않는다
- enrichment 결과를 원본 테이블에 직접 쓰지 않는다 (별도 테이블)
