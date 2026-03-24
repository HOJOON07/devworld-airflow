FROM apache/airflow:3.1.8-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*
USER airflow

COPY requirements.txt /opt/airflow/requirements.txt
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt

COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root src/ /opt/airflow/src/
COPY --chown=airflow:root dbt/ /opt/airflow/dbt/
COPY --chown=airflow:root config/ /opt/airflow/config/

ENV AIRFLOW_HOME=/opt/airflow
