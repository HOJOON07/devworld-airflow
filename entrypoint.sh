#!/bin/bash
set -e

# DB 마이그레이션 (최초 실행 시 테이블 생성, 이후에는 no-op)
airflow db migrate

# 전달받은 명령어 실행 (api-server, scheduler, dag-processor)
exec airflow "$@"
