---
paths:
  - "**/*dlt*/**"
  - "**/*load*/**"
---

# dlt 사용 규칙

dlt 용도:
- structured loading
- incremental structured ingestion
- normalized record loading

dlt로 대체하면 안 되는 것:
- HTML crawling
- source-specific parsing
- 전체 orchestration
- dedup 설계

dlt는 load layer의 일부이지, 전체 파이프라인 자체가 아니다.
