---
paths:
  - "**/*github*/**"
  - "**/github_*"
---

# GitHub 파이프라인 규칙

## 수집
- GitHub REST API + PAT 인증 (.env의 GITHUB_TOKEN)
- 증분 수집: last_collected_at watermark 기반
- PR: state=all, sort=updated, watermark 비교로 중단
- Issue: since 파라미터로 증분
- Issue API에서 pull_request 필드 null인 것만 순수 Issue

## PR diff
- 상위 10개 파일만 patch 수집
- 나머지 파일은 메타만 (filename, status, additions, deletions)
- AI enrichment에도 상위 10개 patch만 전달

## Rate limit
- 5,000 req/hour (PAT)
- 대형 레포: 최초 수집 시 initial_fetch_days로 제한
- 매일 증분: 100~300 req/일

## AI enrichment
- PR: ai_summary, key_changes, impact_analysis, change_type, ai_code_review
- Issue: ai_summary, key_points, suggested_solution, contribution_difficulty
- 기존 ollama_client.py 재사용

## 하지 말 것
- API key를 코드에 하드코딩하지 않는다
- 전체 PR diff를 LLM에 보내지 않는다
- 블로그 크롤링 코드와 GitHub 코드를 섞지 않는다
