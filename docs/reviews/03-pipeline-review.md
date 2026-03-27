# 데이터 파이프라인 코드 리뷰

**리뷰어**: pipeline-reviewer
**리뷰 일자**: 2026-03-27

---

## 리뷰 결과

### Critical (4건)

**C-1. `github_enrich_service.py` 파일 미존재**
- DAG에서 import하지만 파일 없음 → 런타임 ImportError
- 수정: 구현 또는 DAG 비활성화

**C-2. DuckLake/R2 기반 Bronze가 아닌 MinIO filesystem 직접 적재**
- CLAUDE.md: Bronze = R2 + DuckLake. 실제: dlt.destinations.filesystem
- DuckLake catalog 미등록, setup.py 미호출
- 수정: 설계를 현실에 맞추거나, DuckLake 통합 구현

**C-3. dbt Bronze/Silver가 PostgreSQL에서 실행**
- CLAUDE.md: Bronze/Silver = R2 parquet. 실제: PostgreSQL view/table
- "Bronze/Silver 데이터를 RDS에 넣지 않는다" 원칙 위반
- 수정: CLAUDE.md 수정 또는 dbt-duckdb 전환

**C-4. load_service.py write_disposition="replace" + partition 미적용**
- 매 실행마다 소스 전체 데이터를 replace → 비효율 + 유실 위험
- 수정: partition_date 필터 추가 또는 merge/append

### Warning (10건)

- W-1: enrich_service.py가 직접 SQL 실행 (repository 우회)
- W-2: load_service.py도 직접 SQL (application 레이어 위반)
- W-3: airflow.decorators 사용 (deprecated)
- W-4: blog_crawl_dag.py 내부 sync_sources 호출 (불필요 부수효과)
- W-5: GitHub PR watermark 증분 수집 불완전 (max_pages 한계)
- W-6: Article 객체 비교 시 `not in` 사용 (비교 오류 가능)
- W-7: datetime.utcnow() deprecated 사용 (다수 파일)
- W-8: Dedup이 URL + content_hash 2단계만 (설계는 4단계)
- W-9: DuckLake setup 코드 dead code
- W-10: ollama_client.py Prompt Injection 취약성

### Pass (10건)

- Raw First 원칙 (블로그), Thin DAG, 관심사 분리
- Asset 기반 체이닝, CrawlJob 추적, ON CONFLICT upsert
- GitHub API 페이지네이션/Rate limit, 소스 관리 체계
- dbt 테스트 커버리지, 파서 팩토리 패턴

---

## 기술 문서

### 데이터 레이어 매핑 (설계 vs 실제)

| 레이어 | 설계 | 실제 | 괴리 |
|---|---|---|---|
| Raw | MinIO HTML | MinIO HTML (블로그만) | GitHub 미적용 |
| Bronze | R2 + DuckLake parquet | MinIO parquet (dbt 미소비) + PG articles | **불일치** |
| Silver | R2 + DuckLake parquet | PG table | **불일치** |
| Gold Serving | PostgreSQL | PostgreSQL | 일치 |
| Gold Analytics | R2 + DuckLake parquet | 미구현 | N/A |

### 핵심 괴리
**dlt Bronze parquet이 사실상 dead data** — dbt는 PostgreSQL을 직접 읽고, DuckLake는 미통합.

### 개선 우선순위
1. P0: github_enrich_service 구현, partition_date 필터 적용
2. P1: 설계 vs 구현 일치 결정 (Option A or B)
3. P2: repository pattern 적용, deprecated API 전환
4. P3: Near-duplicate detection, Gold Analytics
