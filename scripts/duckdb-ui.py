"""DuckDB UI with MinIO + DuckLake 자동 연결.

로컬에서 실행: make duckdb-ui
브라우저에서 http://localhost:4213 자동 열림
DuckLake catalog + Bronze parquet 바로 조회 가능

환경변수 설정 (또는 .env.local 파일):
  STORAGE_ENDPOINT=localhost:9000
  STORAGE_ACCESS_KEY=minioadmin
  STORAGE_SECRET_KEY=minioadmin
  STORAGE_REGION=us-east-1
  DUCKLAKE_HOST=localhost
  DUCKLAKE_PORT=5433
  DUCKLAKE_DB=airflow_db
  DUCKLAKE_USER=airflow
  DUCKLAKE_PASSWORD=airflow
"""

import os
import duckdb
import time

# 환경변수 (기본값은 로컬 개발용)
S3_ENDPOINT = os.environ.get("STORAGE_ENDPOINT", "localhost:9000")
S3_KEY = os.environ.get("STORAGE_ACCESS_KEY", "minioadmin")
S3_SECRET = os.environ.get("STORAGE_SECRET_KEY", "minioadmin")
S3_REGION = os.environ.get("STORAGE_REGION", "us-east-1")
DL_HOST = os.environ.get("DUCKLAKE_HOST", "localhost")
DL_PORT = os.environ.get("DUCKLAKE_PORT", "5433")
DL_DB = os.environ.get("DUCKLAKE_DB", "airflow_db")
DL_USER = os.environ.get("DUCKLAKE_USER", "airflow")
DL_PASSWORD = os.environ.get("DUCKLAKE_PASSWORD", "airflow")

conn = duckdb.connect()

# Extensions
conn.execute("INSTALL httpfs; LOAD httpfs;")
conn.execute("INSTALL ducklake; LOAD ducklake;")

# S3/MinIO
conn.execute(f"""
    CREATE SECRET my_s3_secret (
        TYPE s3,
        KEY_ID '{S3_KEY}',
        SECRET '{S3_SECRET}',
        REGION '{S3_REGION}',
        ENDPOINT '{S3_ENDPOINT}',
        USE_SSL false,
        URL_STYLE 'path'
    )
""")

# DuckLake catalog
conn.execute(f"""
    ATTACH 'ducklake:postgres:host={DL_HOST} port={DL_PORT} dbname={DL_DB} user={DL_USER} password={DL_PASSWORD}'
    AS ducklake (DATA_PATH 's3://devworld-bronze', METADATA_SCHEMA 'ducklake')
""")

conn.execute("USE ducklake;")

# UI
conn.execute("INSTALL ui; LOAD ui;")
conn.execute("CALL start_ui()")

print("DuckDB UI running on http://localhost:4213")
print(f"MinIO: {S3_ENDPOINT} | DuckLake: {DL_HOST}:{DL_PORT}/{DL_DB}")
print("Press Ctrl+C to stop")

while True:
    time.sleep(3600)
