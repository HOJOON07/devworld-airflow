#!/usr/bin/env bash
# =============================================================================
# Airflow Container Entrypoint
# Shared by webserver and scheduler services.
# Usage in docker-compose:
#   command: ["webserver"]   or   command: ["scheduler"]
# =============================================================================
set -euo pipefail

CONFIG_DIR="/opt/airflow/config"

echo "[entrypoint] Running airflow db migrate ..."
airflow db migrate

# Import connections if template exists
if [ -f "${CONFIG_DIR}/connections.json" ]; then
    echo "[entrypoint] Importing connections from ${CONFIG_DIR}/connections.json ..."
    airflow connections import "${CONFIG_DIR}/connections.json" || true
fi

# Import variables if template exists
if [ -f "${CONFIG_DIR}/variables.json" ]; then
    echo "[entrypoint] Importing variables from ${CONFIG_DIR}/variables.json ..."
    airflow variables import "${CONFIG_DIR}/variables.json" || true
fi

# Create admin user if it does not already exist
if ! airflow users list | grep -q "admin"; then
    echo "[entrypoint] Creating admin user ..."
    airflow users create \
        --username admin \
        --password admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@devworld.local
fi

echo "[entrypoint] Starting: $*"
exec "$@"
