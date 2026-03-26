---
name: ai-enrich
description: Ollama Cloud API를 사용한 아티클 AI enrichment (keywords, topics, summary)
disable-model-invocation: true
argument-hint: "[model_name]"
---

AI enrichment 관련 코드를 작성하거나 수정한다.

## 개요

Silver 아티클(int_articles_cleaned)에서 아직 enrichment 안 된 아티클을 읽어,
Ollama Cloud API로 keywords/topics/summary를 추출하고,
article_enrichments 테이블에 저장한다.

## 데이터 흐름

```
Silver (int_articles_cleaned) → Ollama Cloud API → article_enrichments → Gold (mart_articles JOIN)
```

## 구성 요소

### DAG
- `dags/ai_enrich_dag.py`: 매일 KST 03:00 실행
- 단일 @task로 `enrich_articles(config)` 호출

### Application
- `src/application/enrich_service.py`: Silver에서 미enriched 아티클 조회 → Ollama API 호출 → DB 저장

### Infrastructure
- `src/infrastructure/ai/ollama_client.py`: Ollama Cloud API SDK 클라이언트
- 모델: `qwen3.5:397b` (OLLAMA_MODEL 환경변수)
- 호스트: `https://ollama.com`
- 인증: Bearer token (OLLAMA_API_KEY 환경변수)

## Enrichment 결과 스키마

```sql
article_enrichments (
    article_id UUID PRIMARY KEY,
    keywords JSONB,       -- ["keyword1", "keyword2", ...]
    topics JSONB,         -- ["AI/ML", "DevOps", ...]
    summary TEXT,          -- 2-3문장 한국어 요약
    enriched_at TIMESTAMP
)
```

## 구현 규칙
- Silver 테이블(int_articles_cleaned)에서 읽기, Raw/Bronze에서 직접 읽지 않는다
- UPSERT 사용 (ON CONFLICT article_id DO UPDATE)
- content_text 첫 3000자만 LLM에 전달
- JSON 응답 파싱: 코드블록 제거, json.loads, 실패 시 빈 결과 반환
- OLLAMA_API_KEY 없으면 skip (warning 로그)

## 환경변수
- `OLLAMA_API_KEY`: Ollama Cloud API 키
- `OLLAMA_MODEL`: 사용할 모델 (기본값: qwen3.5:397b)

## 하지 말 것
- enrichment 결과를 Silver 테이블에 직접 넣지 않는다 (별도 테이블)
- Raw HTML을 LLM에 전달하지 않는다 (content_text만)
- API 호출 실패 시 전체 DAG을 중단하지 않는다 (개별 아티클 skip)

## 검증
- article_enrichments 테이블에 결과 확인
- Gold mart_articles에서 keywords/topics/ai_summary JOIN 확인
