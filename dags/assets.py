from airflow.sdk import Asset

# Pipeline assets — 논리적 이름으로 정의 (URI scheme 충돌 방지)
articles_ready = Asset("devworld://articles")
bronze_ready = Asset("devworld://bronze")
silver_ready = Asset("devworld://silver")
enrichments_ready = Asset("devworld://enrichments")
gold_ready = Asset("devworld://gold")
