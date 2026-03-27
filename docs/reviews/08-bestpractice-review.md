# Best Practice 리뷰

**리뷰어**: bestpractice-reviewer
**리뷰 일자**: 2026-03-27

---

## Best Practice 준수도 점수표

| 영역 | 점수 (10점) | 판정 |
|---|---|---|
| ELT 파이프라인 패턴 | 5/10 | 부분 준수 |
| Medallion Architecture | 4/10 | 부분 준수 |
| Airflow DAG 설계 | 8/10 | 준수 |
| dbt 모델링 | 6/10 | 부분 준수 |
| dlt 적재 | 6/10 | 부분 준수 |
| 데이터 품질 | 5/10 | 부분 준수 |
| 보안 | 4/10 | 미준수 |
| 확장성/모듈화 | 8/10 | 준수 |
| 모니터링/관측성 | 3/10 | 미준수 |
| 테스트 | 6/10 | 부분 준수 |
| **종합** | **5.5/10** | **부분 준수** |

---

## 핵심 판단

> 아키텍처 설계 의도는 매우 좋다. Clean Architecture, Protocol 인터페이스, Asset-driven DAG, source config 패턴 등은 업계 best practice에 부합.
> **가장 큰 과제는 "설계 문서와 구현의 괴리".**

## 강점

- **Airflow 8/10**: Asset 기반 트리거, Dynamic Task Mapping, Thin DAG, Cosmos, CrawlJob 추적
- **확장성 8/10**: Clean Architecture, Protocol 인터페이스, sources.yml 패턴, Parser Factory
- **Raw First 원칙**: 블로그 파이프라인에서 올바르게 구현

## 약점

- **보안 4/10**: .env 토큰 노출, 평문 자격증명, admin/admin
- **모니터링 3/10**: 구조화 로깅 없음, 메트릭 없음, 알림 없음
- **Medallion 4/10**: Bronze parquet dead data, Silver = PostgreSQL, Gold Analytics 미구현

---

## PostgreSQL 중심 vs Lakehouse 트레이드오프

| 기준 | PostgreSQL 중심 (현재) | Lakehouse (DuckLake) |
|---|---|---|
| 운영 복잡도 | 낮음 | 중간 |
| 비용 (현재 규모) | 낮음 | 불필요한 비용 |
| 쿼리 성능 (OLTP) | 최적 | PG 유지 |
| 쿼리 성능 (OLAP) | 한계 | 우수 |
| 시간 여행/버전 관리 | 불가 | 가능 |
| 전환 임계점 | - | articles > 50만 행 |

**권고**: 현재 규모(수천 건)에서 PostgreSQL 중심은 합리적. Lakehouse 전환은 규모 증가 시.

---

## 개선 로드맵

### Phase 1: 즉시 (보안 + 안정성)
1. github_enrich_service.py 구현
2. DAG retry/timeout 설정
3. airflow.sdk 마이그레이션
4. 자격증명 하드코딩 제거
5. dbt source freshness 설정
6. 실패 알림 설정

### Phase 2: 아키텍처 정합성
7. CLAUDE.md 레이어 매핑 현실화 (Option A)
8. Silver incremental materialization
9. dbt schema 분리 (bronze/silver/public)
10. GitHub Protocol/Interface 추가

### Phase 3: 확장성
11. DuckLake 도입 (조건부)
12. Near-duplicate detection
13. 구조화 로깅
14. Playwright 도입

---

## 최종 권고 아키텍처

```
[현재 규모에 적합한 Pragmatic PostgreSQL 중심]

Sources → Crawler → MinIO/R2 (raw 보관) + PostgreSQL (Bronze/Silver/Gold)
                                                ↓
                                          Nest.js API
```

CLAUDE.md 업데이트:
- Phase 1: PostgreSQL 중심 (현재)
- Phase 2: DuckLake 전환 (규모 증가 시)

전환 트리거: articles > 50만 행, dbt run > 5분, 분석 쿼리 빈도 증가
