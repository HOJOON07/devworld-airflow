# Medallion Architecture Best Practice

**작성일**: 2026-03-31
**참고**: Microsoft/Databricks 공식 문서 + 실무 적용

---

## 개요

Medallion Architecture는 데이터의 품질을 단계적으로 높이는 설계 패턴이다.

```
Raw (데이터 레이크)  →  Bronze (정형화)  →  Silver (정제)  →  Gold (비즈니스)  →  Serving (API)
```

각 레이어는 명확한 책임이 있고, **중복 제거와 데이터 품질은 레이어별로 분리**한다.

---

## 레이어별 원칙

### Raw (데이터 레이크)

```
저장소: R2/MinIO (devworld-raw)
포맷: HTML, JSON (비정형)
원칙: 원본 보존, 변환 없음
```

| 항목 | 원칙 |
|---|---|
| 쓰기 | 수집 즉시 저장 |
| 중복 | 허용 (같은 URL을 2번 크롤링할 수 있음) |
| 삭제 | 하지 않음 |
| 용도 | 재처리, 감사, 백업 |

### Bronze (정형화)

```
저장소: DuckLake (devworld-lake, Parquet)
도구: dlt
원칙: Append-only, 증분 적재, 중복 허용
```

| 항목 | 원칙 | 이유 |
|---|---|---|
| **쓰기 방식** | Append-only | 원본 보존. 데이터를 수정/삭제하지 않음 |
| **중복** | 허용 | 같은 article이 2번 들어올 수 있음. 중복 제거는 Silver의 책임 |
| **증분 처리** | dlt incremental | 마지막 적재 이후의 새 데이터만 가져옴 (watermark 기반) |
| **스키마** | 최소 변환 | text/string 위주. 타입 캐스팅은 Silver에서 |
| **메타데이터** | 적재 시점 기록 | `crawled_at` 컬럼 추가 |
| **dbt 테스트** | unique 테스트 없음 | Bronze는 raw 데이터이므로 unique 보장하지 않음 |

**증분 처리 패턴 (dlt incremental):**

```python
@dlt.resource(name="articles", write_disposition="append")
def _resource():
    yield from dlt.sources.incremental(
        "discovered_at",                    # 증분 기준 컬럼
        initial_value="2000-01-01T00:00:00" # 최초 실행 시 전체 로드
    ).filter_items(records)
```

- dlt가 pipeline state로 마지막 `discovered_at` 값을 자동 추적
- 다음 실행 시 그 이후 데이터만 yield
- 같은 데이터를 2번 실행해도 중복 적재 안 됨

**왜 merge가 아닌 append인가:**

| 방식 | 장점 | 단점 |
|---|---|---|
| append + incremental | 빠름, 단순, 이력 보존 | Silver에서 dedup 필요 |
| merge (upsert) | 중복 없음 | 느림, 데이터 커지면 비효율, 이력 손실 |
| replace | 가장 단순 | 전체 교체, 데이터 유실 위험 |

**Best Practice: append + incremental** — Bronze는 빠르게 쌓고, 정제는 Silver에서.

---

### Silver (정제 + Dedup)

```
저장소: DuckLake (devworld-lake, Parquet)
도구: dbt
원칙: 중복 제거, 타입 변환, 품질 검증
```

| 항목 | 원칙 | 이유 |
|---|---|---|
| **쓰기 방식** | Full rebuild (materialized='table') | 데이터 규모가 작으면 전체 재생성이 안전하고 단순 |
| **중복 제거** | ROW_NUMBER PARTITION BY | PK 또는 content_hash 기준으로 최신/최초 1건만 유지 |
| **타입 변환** | 여기서 수행 | text → timestamp, uuid 등 |
| **품질 검증** | NOT NULL, UNIQUE 테스트 | Silver 이후로는 중복이 없어야 함 |
| **정규화** | 여기서 수행 | 중첩 JSON → 플랫 컬럼 |

**Dedup 패턴 (ROW_NUMBER):**

```sql
-- int_articles_cleaned.sql
WITH ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY content_hash
            ORDER BY discovered_at ASC
        ) AS rn
    FROM {{ ref('stg_articles') }}
    WHERE content_hash IS NOT NULL
)
SELECT * FROM ranked WHERE rn = 1
```

- `content_hash` 기준으로 중복 제거
- `discovered_at ASC`로 최초 수집된 것을 유지
- Bronze에 100건이 있어도 Silver에는 unique한 80건만

**Silver에서 데이터가 커지면:**

- `materialized='table'` → `materialized='incremental'`로 전환
- dbt incremental은 `unique_key` 기준으로 upsert

```sql
{{ config(
    materialized='incremental',
    unique_key='content_hash',
    incremental_strategy='delete+insert'
) }}
```

---

### Gold (비즈니스 마트)

```
저장소: DuckLake (devworld-lake, Parquet)
도구: dbt
원칙: Full rebuild, JOIN + 집계, 비즈니스 로직
```

| 항목 | 원칙 | 이유 |
|---|---|---|
| **쓰기 방식** | Full rebuild | 집계/JOIN 결과는 매번 재생성이 안전 |
| **JOIN** | Silver + enrichments | 여러 테이블을 denormalize |
| **집계** | 여기서 수행 | COUNT, SUM, AVG 등 비즈니스 집계 |
| **기간 필터** | 필요 시 적용 | 최근 7일, 30일 등 |

**Gold 모델 패턴:**

```sql
-- mart_articles.sql
SELECT
    a.*,
    e.keywords,
    e.topics,
    e.summary as ai_summary
FROM {{ ref('int_articles_cleaned') }} a
LEFT JOIN {{ source('app_db', 'article_enrichments') }} e
    ON a.id = e.article_id
```

**Gold에서 데이터가 커지면:**
- 전체 rebuild가 느려지면 incremental로 전환
- 또는 기간 필터 적용 (최근 90일만)

---

### Serving (데이터 마트)

```
저장소: PostgreSQL app_db.serving
도구: dbt reverse_etl
원칙: 매번 재생성, API 최적화
```

| 항목 | 원칙 | 이유 |
|---|---|---|
| **쓰기 방식** | DROP + CREATE (전체 교체) | API가 읽는 테이블이므로 일관성 중요 |
| **인덱스** | FTS (tsvector + GIN) | 검색 성능 최적화 |
| **정리** | reverse_etl 전에 CASCADE DROP | DuckDB postgres extension이 PG 인덱스를 인식 못하는 문제 방지 |

**Serving 실행 순서:**

```
cleanup_serving_tables (DROP CASCADE)
    ↓
reverse_etl (dbt: Gold → PG)
    ↓
create_fts_index (ALTER TABLE + GIN)
```

---

## 정리: 레이어별 비교표

| 항목 | Bronze | Silver | Gold | Serving |
|---|---|---|---|---|
| **쓰기** | append-only | full rebuild | full rebuild | DROP + CREATE |
| **중복** | 허용 | 제거 (ROW_NUMBER) | 없음 (Silver 보장) | 없음 |
| **증분** | dlt incremental | full (→ incremental 가능) | full | full |
| **테스트** | not_null만 | unique + not_null | unique + not_null | — |
| **변환** | 최소 | 타입변환 + dedup | JOIN + 집계 | FTS 인덱스 |
| **재처리** | raw부터 재적재 | Bronze부터 재빌드 | Silver부터 재빌드 | Gold부터 재export |

---

## 우리 프로젝트 적용

```
blog_crawl_all (크롤링)
    ↓ articles → PostgreSQL (운영 DB)
    ↓ Raw HTML → MinIO (데이터 레이크)

dlt_load (Bronze 적재)
    ↓ dlt incremental(discovered_at) — 새 데이터만 append
    ↓ → DuckLake Bronze (append-only, 중복 허용)

dbt_silver (Silver 변환)
    ↓ ROW_NUMBER PARTITION BY content_hash — dedup
    ↓ → DuckLake Silver (unique 보장)

ai_enrich (AI Enrichment)
    ↓ Silver에서 읽기 → Ollama API → PG enrichments

dbt_gold (Gold 변환)
    ↓ Silver LEFT JOIN enrichments — denormalize
    ↓ → DuckLake Gold (비즈니스 마트)

reverse_etl (Serving Export)
    ↓ cleanup → Gold → PG serving → FTS 인덱스
    ↓ → PostgreSQL serving (API 조회용)
```

## 참고 자료

- [Microsoft: Medallion Lakehouse Architecture](https://learn.microsoft.com/en-us/azure/databricks/lakehouse/medallion)
- Databricks: "Bronze layer is appended incrementally and grows over time"
- Databricks: "Data cleanup and validation are performed in silver layer"
- Databricks: "Gold layer consists of aggregated data tailored for analytics"
