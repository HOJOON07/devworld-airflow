---
paths:
  - "**/*dbt*/**"
  - "**/*transform*/**"
  - "**/*models*/**"
---

# dbt 사용 규칙

dbt 용도:
- bronze → silver transformation
- silver → gold marts
- analytical models
- serving-oriented analytical tables
- data test

dbt로 하면 안 되는 것:
- raw crawling
- HTML parsing
- source-specific extraction

dbt는 transformation layer에 속한다. extraction layer가 아니다.
