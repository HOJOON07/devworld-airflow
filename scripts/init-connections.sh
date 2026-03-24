#!/usr/bin/env bash
# =============================================================================
# Initialize Airflow Connections and Variables
# For local development environment setup.
# Run this manually after containers are up if you need to re-import.
# =============================================================================
set -euo pipefail

CONFIG_DIR="/opt/airflow/config"

echo "[init] Importing connections ..."
airflow connections import "${CONFIG_DIR}/connections.json"

echo "[init] Importing variables ..."
airflow variables import "${CONFIG_DIR}/variables.json"

echo "[init] Done."
