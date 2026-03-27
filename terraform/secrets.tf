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
