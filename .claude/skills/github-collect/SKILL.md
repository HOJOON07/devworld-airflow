---
name: github-collect
description: GitHub API 수집 코드 작성 가이드
disable-model-invocation: true
---

GitHub API에서 PR/Issue를 수집하는 코드를 작성한다.

## 데이터 흐름

```
GitHub REST API (PAT) → PostgreSQL (github_prs, github_issues, github_pr_files)
                      → MinIO Bronze parquet (dlt 적재)
```

## 수집 대상

### PR
- 엔드포인트: GET /repos/{owner}/{repo}/pulls?state=all&sort=updated&per_page=100
- since 미지원 → sort=updated로 정렬 후 watermark 비교
- PR 상세: GET /repos/{owner}/{repo}/pulls/{number}
- PR 파일: GET /repos/{owner}/{repo}/pulls/{number}/files
  - 상위 10개만 patch 수집, 나머지는 메타만

### Issue
- 엔드포인트: GET /repos/{owner}/{repo}/issues?state=all&sort=updated&since={watermark}
- since 파라미터 지원
- pull_request 필드가 null인 것만 순수 Issue

## 증분 수집
- github_repos.last_collected_at을 watermark로 사용
- 최초 수집: initial_fetch_days (기본 30일)
- 매일: watermark 이후 updated된 것만

## 인증
- PAT: .env의 GITHUB_TOKEN
- Rate limit: 5,000 req/hour

## 하지 말 것
- API key를 코드에 하드코딩하지 않는다
- 전체 PR diff를 저장하지 않는다 (상위 10개 파일만)
- closed된 지 오래된 PR/Issue를 매번 재수집하지 않는다
