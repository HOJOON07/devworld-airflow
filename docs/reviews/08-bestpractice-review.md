# Best Practice 리뷰

**리뷰어**: bestpractice-reviewer
**리뷰 일자**: 2026-03-27
**수정 일자**: 2026-03-29 (DuckLake 전환 후)

---

## Best Practice 준수도 점수표

| 영역 | 이전 | 현재 | 변동 | 판정 |
|---|---|---|---|---|
| ELT 파이프라인 패턴 | 5/10 | 8/10 | +3 | 준수 |
| Medallion Architecture | 4/10 | 8/10 | +4 | 준수 |
| Airflow DAG 설계 | 8/10 | 8/10 | 0 | 준수 |
| dbt 모델링 | 6/10 | 7/10 | +1 | 부분 준수 |
| dlt 적재 | 6/10 | 8/10 | +2 | 준수 |
| 데이터 품질 | 5/10 | 5/10 | 0 | 부분 준수 |
| 보안 | 4/10 | 7/10 | +3 | 부분 준수 |
| 확장성/모듈화 | 8/10 | 8/10 | 0 | 준수 |
| 모니터링/관측성 | 3/10 | 5/10 | +2 | 부분 준수 |
| 테스트 | 6/10 | 6/10 | 0 | 부분 준수 |
| **종합** | **5.5/10** | **7.0/10** | **+1.5** | **부분 준수** |

---

## 핵심 판단

> DuckLake 전환으로 "설계 문서와 구현의 괴리"가 크게 해소되었다.
> ELT 파이프라인이 Bronze → Silver → Gold → Serving 경로를 정상적으로 따르며,
> Medallion Architecture가 물리적 레이어로 구분된다.
> 남은 과제는 DAG 코드 품질(Thin DAG), 데이터 품질 검증, DAG 레벨 알림 연동이다.

---

## 영역별 점수 변동 상세

### ELT 파이프라인: 5 → 8 (+3)
- dlt → DuckLake Bronze, dbt → Silver/Gold, reverse_etl → PG serving
- 감점: reverse_etl ref() 미사용 (-1), enrichment가 PG 경유 (-1)

### Medallion Architecture: 4 → 8 (+4)
- Bronze/Silver/Gold가 DuckLake 별도 스키마로 물리적 분리
- Bronze parquet이 실제 소비됨 (이전 dead data)
- 감점: article_enrichments가 DuckLake 외부 (-1), Gold Analytics 미구현 (-1)

### 보안: 4 → 7 (+3)
- .dockerignore, Fernet key, EXPOSE_CONFIG=false, Secrets Manager (Terraform)
- 감점: docker-compose에 Fernet key 평문 (-1), MinIO credentials 하드코딩 (-1), profiles.yml 기본값 노출 (-1)

### 모니터링: 3 → 5 (+2)
- CloudWatch 알람 4개 + SNS email 알림 구축
- 감점: DAG on_failure_callback 미연동 (-2), 구조화 로깅 부재 (-1.5), 메트릭 없음 (-1), source freshness 없음 (-0.5)

---

## 개선 로드맵 (업데이트)

### 완료됨
- [x] DuckLake 도입 (Bronze/Silver/Gold)
- [x] dbt schema 분리 (bronze/silver/gold/serving)
- [x] airflow.sdk 마이그레이션
- [x] 자격증명 Secrets Manager 이관 (Terraform)
- [x] EXPOSE_CONFIG=false
- [x] Fernet key 설정
- [x] SNS 알람 인프라 구축
- [x] reverse_etl 레이어 구현

### Phase 1: 즉시 (코드 품질 + 안정성)
1. github_enrich_service.py 구현
2. Thin DAG — crawl 로직 서비스 추출
3. DAG retry/timeout 설정
4. reverse_etl에서 ref() 사용
5. datetime.utcnow → datetime.now(UTC)
6. DUCKLAKE_DATA_PATH 통일 (devworld-lake)

### Phase 2: 데이터 품질 + 모니터링
7. DAG on_failure_callback → SNS/Slack
8. dbt source freshness 설정
9. Silver incremental materialization
10. 구조화 로깅 (JSON)
11. write_disposition → merge/append

### Phase 3: 확장성
12. Near-duplicate detection
13. GitHub Pipeline DuckLake 전환
14. Gold Analytics 레이어
15. CI/CD (GitHub Actions)

---

## 최종 아키텍처

```
Sources → Crawler → MinIO/R2 (Raw HTML)
                 → PostgreSQL (articles, crawl_sources, enrichments)
                                    ↓ dlt (ducklake)
                              DuckLake (Bronze → Silver → Gold)
                                    ↓ reverse_etl
                              PostgreSQL serving (FTS + GIN)
                                    ↓
                              Nest.js API
```
