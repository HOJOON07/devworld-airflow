resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "${var.project_name}/db-credentials"
  description = "Database credentials for RDS PostgreSQL"

  tags = {
    Name = "${var.project_name}-db-credentials"
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  secret_string = jsonencode({
    username          = aws_db_instance.main.username
    password          = random_password.db_password.result
    host              = aws_db_instance.main.address
    port              = aws_db_instance.main.port
    dbname            = aws_db_instance.main.db_name
    connection_string = "postgresql+psycopg2://${aws_db_instance.main.username}:${random_password.db_password.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${aws_db_instance.main.db_name}"
  })
}

resource "aws_secretsmanager_secret" "airflow_secret_key" {
  name        = "${var.project_name}/airflow-secret-key"
  description = "Airflow API server secret key"

  tags = {
    Name = "${var.project_name}-airflow-secret-key"
  }
}

resource "aws_secretsmanager_secret_version" "airflow_secret_key" {
  secret_id     = aws_secretsmanager_secret.airflow_secret_key.id
  secret_string = random_password.airflow_secret_key.result
}

resource "random_password" "airflow_secret_key" {
  length  = 64
  special = false
}

resource "random_password" "fernet_key" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "fernet_key" {
  name        = "${var.project_name}/airflow-fernet-key"
  description = "Airflow Fernet encryption key"

  tags = {
    Name = "${var.project_name}-airflow-fernet-key"
  }
}

resource "aws_secretsmanager_secret_version" "fernet_key" {
  secret_id     = aws_secretsmanager_secret.fernet_key.id
  secret_string = base64encode(random_password.fernet_key.result)
}

resource "aws_secretsmanager_secret" "github_token" {
  name        = "${var.project_name}/github-token"
  description = "GitHub Personal Access Token for PR/Issue collection"

  tags = {
    Name = "${var.project_name}-github-token"
  }
}

# github_token의 값은 terraform apply 후 수동 설정:
# aws secretsmanager put-secret-value --secret-id devworld/github-token --secret-string "ghp_xxx"

resource "aws_secretsmanager_secret" "ollama_api_key" {
  name        = "${var.project_name}/ollama-api-key"
  description = "Ollama Cloud API key for AI enrichment"

  tags = {
    Name = "${var.project_name}-ollama-api-key"
  }
}

# ollama_api_key의 값은 terraform apply 후 수동 설정:
# aws secretsmanager put-secret-value --secret-id devworld/ollama-api-key --secret-string "xxx"

resource "aws_secretsmanager_secret" "r2_credentials" {
  name        = "${var.project_name}/r2-credentials"
  description = "Cloudflare R2 access credentials (placeholder)"

  tags = {
    Name = "${var.project_name}-r2-credentials"
  }
}

resource "aws_secretsmanager_secret_version" "r2_credentials" {
  secret_id = aws_secretsmanager_secret.r2_credentials.id

  secret_string = jsonencode({
    access_key_id     = "CHANGE_ME"
    secret_access_key = "CHANGE_ME"
    endpoint          = "CHANGE_ME"
    bucket            = "devworld"
  })
}

resource "aws_secretsmanager_secret" "ducklake_catalog_url" {
  name        = "${var.project_name}/ducklake-catalog-url"
  description = "DuckLake catalog connection string (libpq format, airflow_db)"

  tags = {
    Name = "${var.project_name}-ducklake-catalog-url"
  }
}

resource "aws_secretsmanager_secret_version" "ducklake_catalog_url" {
  secret_id     = aws_secretsmanager_secret.ducklake_catalog_url.id
  secret_string = "host=${aws_db_instance.main.address} port=${aws_db_instance.main.port} dbname=${var.db_name} user=${aws_db_instance.main.username} password=${random_password.db_password.result}"
}

resource "aws_secretsmanager_secret" "app_db_url" {
  name        = "${var.project_name}/app-db-url"
  description = "App DB connection URL (postgresql:// format for dbt reverse_etl)"

  tags = {
    Name = "${var.project_name}-app-db-url"
  }
}

resource "aws_secretsmanager_secret_version" "app_db_url" {
  secret_id     = aws_secretsmanager_secret.app_db_url.id
  secret_string = "postgresql://${aws_db_instance.main.username}:${random_password.db_password.result}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/app_db"
}
