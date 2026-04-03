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

resource "aws_secretsmanager_secret" "airflow_jwt_secret" {
  name        = "${var.project_name}/airflow-jwt-secret"
  description = "Airflow API Auth JWT secret for Execution API authentication"

  tags = {
    Name = "${var.project_name}-airflow-jwt-secret"
  }
}

resource "aws_secretsmanager_secret_version" "airflow_jwt_secret" {
  secret_id     = aws_secretsmanager_secret.airflow_jwt_secret.id
  secret_string = random_password.airflow_jwt_secret.result
}

resource "random_password" "airflow_jwt_secret" {
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

# ─── NestJS API Secrets ───

resource "aws_secretsmanager_secret" "nestjs_platform_db" {
  name        = "${var.project_name}/nestjs-platform-db"
  description = "NestJS platform database name"

  tags = {
    Name = "${var.project_name}-nestjs-platform-db"
  }
}

resource "aws_secretsmanager_secret_version" "nestjs_platform_db" {
  secret_id = aws_secretsmanager_secret.nestjs_platform_db.id
  secret_string = jsonencode({
    dbname = "platform_db"
  })
}

resource "aws_secretsmanager_secret" "nestjs_app_db" {
  name        = "${var.project_name}/nestjs-app-db"
  description = "NestJS pipeline (app_db) database name"

  tags = {
    Name = "${var.project_name}-nestjs-app-db"
  }
}

resource "aws_secretsmanager_secret_version" "nestjs_app_db" {
  secret_id = aws_secretsmanager_secret.nestjs_app_db.id
  secret_string = jsonencode({
    dbname = "app_db"
  })
}

resource "aws_secretsmanager_secret" "nestjs_jwt_secrets" {
  name        = "${var.project_name}/nestjs-jwt-secrets"
  description = "NestJS JWT access and refresh secrets"

  tags = {
    Name = "${var.project_name}-nestjs-jwt-secrets"
  }
}

# JWT secrets — terraform apply 후 수동 설정:
# aws secretsmanager put-secret-value --secret-id devworld/nestjs-jwt-secrets \
#   --secret-string '{"access_secret":"<32+ chars>","refresh_secret":"<32+ chars>"}'

resource "aws_secretsmanager_secret" "nestjs_github_oauth" {
  name        = "${var.project_name}/nestjs-github-oauth"
  description = "NestJS GitHub OAuth client credentials"

  tags = {
    Name = "${var.project_name}-nestjs-github-oauth"
  }
}

# GitHub OAuth — terraform apply 후 수동 설정:
# aws secretsmanager put-secret-value --secret-id devworld/nestjs-github-oauth \
#   --secret-string '{"client_id":"xxx","client_secret":"xxx"}'

# NestJS Encryption Key (for user AI keys encryption)
resource "aws_secretsmanager_secret" "nestjs_encryption_key" {
  name        = "${var.project_name}/nestjs-encryption-key"
  description = "NestJS encryption key for user AI keys"

  tags = {
    Name = "${var.project_name}-nestjs-encryption-key"
  }
}
