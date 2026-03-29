"""DuckDB UI with MinIO + DuckLake 자동 연결.

로컬에서 실행: make duckdb-ui
브라우저에서 http://localhost:4213 자동 열림
DuckLake catalog + Bronze/Silver/Gold parquet 바로 조회 가능

환경변수 설정 (또는 .env.local 파일):
  STORAGE_ENDPOINT=localhost:9000
  STORAGE_ACCESS_KEY=minioadmin
  STORAGE_SECRET_KEY=minioadmin
  STORAGE_REGION=us-east-1
  DUCKLAKE_PG_HOST=localhost
  DUCKLAKE_PG_PORT=5433
  DUCKLAKE_PG_DBNAME=airflow_db
  DUCKLAKE_DATA_PATH=s3://devworld-lake/
"""

import os
import time

import duckdb

# S3/MinIO config
S3_ENDPOINT = os.environ.get("STORAGE_ENDPOINT", "localhost:9000")
S3_KEY = os.environ.get("STORAGE_ACCESS_KEY", "minioadmin")
S3_SECRET = os.environ.get("STORAGE_SECRET_KEY", "minioadmin")
S3_REGION = os.environ.get("STORAGE_REGION", "us-east-1")

# DuckLake config
PG_HOST = os.environ.get("DUCKLAKE_PG_HOST", "localhost")
PG_PORT = os.environ.get("DUCKLAKE_PG_PORT", "5433")
PG_DBNAME = os.environ.get("DUCKLAKE_PG_DBNAME", "airflow_db")
PG_USER = os.environ.get("POSTGRES_USER", "airflow")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "airflow")
DATA_PATH = os.environ.get("DUCKLAKE_DATA_PATH", "s3://devworld-lake/")


def _esc(value: str) -> str:
    """Escape single quotes for safe SQL string interpolation."""
    return value.replace("'", "''")


conn = duckdb.connect()

# Extensions — postgres must be loaded before ducklake
conn.execute("INSTALL postgres; LOAD postgres;")
conn.execute("INSTALL httpfs; LOAD httpfs;")
conn.execute("INSTALL ducklake; LOAD ducklake;")

# S3/MinIO
conn.execute(f"""
    CREATE SECRET my_s3_secret (
        TYPE s3,
        KEY_ID '{_esc(S3_KEY)}',
        SECRET '{_esc(S3_SECRET)}',
        REGION '{_esc(S3_REGION)}',
        ENDPOINT '{_esc(S3_ENDPOINT)}',
        USE_SSL false,
        URL_STYLE 'path'
    )
""")

# DuckLake catalog — ducklake:postgres: prefix + libpq params
conn.execute(f"""
    ATTACH 'ducklake:postgres:dbname={_esc(PG_DBNAME)} host={_esc(PG_HOST)} port={_esc(PG_PORT)} user={_esc(PG_USER)} password={_esc(PG_PASSWORD)}'
    AS devworld_lake (DATA_PATH '{_esc(DATA_PATH)}', METADATA_SCHEMA 'devworld_lake')
""")

conn.execute("USE devworld_lake;")

# UI
conn.execute("INSTALL ui; LOAD ui;")
conn.execute("CALL start_ui()")

print("DuckDB UI running on http://localhost:4213")
print(f"MinIO: {S3_ENDPOINT} | DuckLake: {PG_DBNAME}@{PG_HOST}:{PG_PORT}")
print("Bronze/Silver/Gold: devworld_lake.bronze / silver / gold")
print("Press Ctrl+C to stop")

while True:
    time.sleep(3600)
