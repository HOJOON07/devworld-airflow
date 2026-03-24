# CLAUDE.md

## 프로젝트 개요

devworld 플랫폼의 **데이터 ETL 파이프라인 레포**.
테크 기업 블로그 크롤링 + GitHub 오픈소스 issue/PR 트래킹을 통해
인사이트/트렌드/키워드/원문 아티클을 생성한다.

이 레포에 Frontend(Next.js), Backend(Nest.js) 코드는 없다.
Frontend는 Vercel, Backend는 별도 ECS 서비스로 배포된다.

---

## 기술 스택

- **Language**: Python 3.11+
- **Orchestration**: Apache Airflow (LocalExecutor)
- **Load**: dlt
- **Transform**: dbt
- **DB**: PostgreSQL (RDS) — 운영 메타데이터 + Airflow 백엔드 + DuckLake catalog
- **Lakehouse**: DuckLake (catalog: PostgreSQL, storage: R2, parquet 기반)
- **Object Storage**: MinIO (dev) / Cloudflare R2 (prod)
- **Infra**: AWS, ECS Fargate, Docker, Terraform, ECR, ALB, CloudWatch, Secrets Manager
- **Lint/Format**: ruff, black
- **Test**: pytest

## Airflow 실행 방식

- Executor: **LocalExecutor** (scheduler에서 직접 태스크 실행)
- 구성: webserver + scheduler (ECS Fargate 각 1개 서비스)
- **미사용**: worker, triggerer, Redis, CeleryExecutor
- **deferrable operator 전제 설계 금지**
- DAG 배포: Docker image에 포함하여 ECR push → ECS redeploy
- 전환 기준: 동시 태스크 수십 개 이상 시 CeleryExecutor + Redis 도입 검토
- 명시적 요청 없이 Redis/Celery/triggerer를 도입하지 않는다

---

## 데이터 흐름

```
discovery → fetch → parse → normalize → dedup → load(dlt) → transform(dbt) → serve
```

각 단계는 명확히 분리한다. 하나의 모듈/태스크에 여러 책임을 몰아넣지 않는다.

## 데이터 아키텍처 핵심 원칙

1. **Raw First**: 변환 전에 raw(HTML/JSON/metadata)를 반드시 먼저 저장. 원본 없이 파싱 결과만 저장하는 구조 금지
2. **재처리 가능**: 모든 단계는 raw 기준으로 replay 가능해야 한다 (bootstrap, backfill, 재파싱, 재enrichment)
3. **Thin DAG**: DAG는 orchestration만 담당. 비즈니스 로직은 Python 모듈로 분리
4. **Source별 확장**: 공통 추상화를 유지하되 source별 override 가능하게 설계
5. **Dedup은 다층**: URL dedup → content hash → near-duplicate → update/version detection. duplicate와 update를 구분할 것

## 데이터 레이어와 저장소 매핑

| 레이어 | 역할 | 저장소 | 포맷 |
|---|---|---|---|
| **Raw** | 원본 보존 | R2 (dev: MinIO) | HTML, JSON, metadata |
| **Bronze** | raw 정형화 | R2 + DuckLake | parquet |
| **Silver** | 정규화/정제 | R2 + DuckLake | parquet |
| **Gold Serving** | 프로덕트 서빙용 | **PostgreSQL (RDS)** | 테이블 |
| **Gold Analytics** | 분석/통계용 | R2 + DuckLake | parquet |

> Gold를 "집계 전용"으로 오해하지 말 것. 아티클 단위 서빙 데이터도 Gold에 포함.

**서빙 경로**: R2 raw → ETL(DuckDB 엔진) → R2 parquet(bronze/silver) → dbt → Gold Serving을 PostgreSQL에 적재 → Nest.js API가 조회

**DuckDB/DuckLake**: 상주 서버가 아닌 ETL 컨테이너 내부의 분석 엔진. catalog은 PostgreSQL, 데이터는 R2 parquet.

**PostgreSQL 역할 정리**:
- `app_db`: Gold Serving 데이터 (Nest.js가 조회)
- `airflow_db`: Airflow 메타데이터
- DuckLake catalog
- 운영 메타데이터 (crawl source, job status, article registry, dedup metadata)

---

## 저장소 구조

| 레이어 | 포함 내용 |
|---|---|
| `domain` | entity, interface/protocol, 핵심 규칙 |
| `application` | use case, 서비스 흐름, orchestration 로직 |
| `infrastructure` | fetcher, parser, repository, storage adapter, DB 구현체 |
| `shared` | config, logging, normalization/hashing helper |

- domain에 infrastructure 구현 상세를 넣지 않는다
- DAG 파일에 business logic을 넣지 않는다
- shared에 source-specific 로직을 결합하지 않는다

---

## 하지 말 것

- raw와 parsed storage를 하나로 합치기
- raw source-of-truth를 version 없이 overwrite
- business logic을 DAG에 강하게 결합
- 명시적 요청 없이 Redis/Celery/triggerer 도입
- gold를 aggregation-only로 취급
- 모든 source가 같은 구조라고 가정
- single-company logic을 shared pipeline에 박기
- 필요 이상으로 인프라 복잡도 올리기
- storage key, schema 의미, dedup 의미를 조용히 변경
- Bronze/Silver 데이터를 RDS에 넣기 (R2 + DuckLake 영역)
- DuckDB/DuckLake를 서비스 DB 대체재로 쓰기 (ETL/분석 전용)

## 변경 시 원칙

- 아키텍처 영향이 큰 변경은 구현 전 설계 노트 먼저
- source-specific 동작은 격리
- 명시적으로 바뀐 게 아니면 현재 스택 가정 유지
- 헷갈리면: raw 보존이 안전한 쪽, backfill이 쉬운 쪽, 디버깅이 쉬운 쪽
