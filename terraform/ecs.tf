resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-cluster"
  }
}

# Airflow API Server Task Definition
resource "aws_ecs_task_definition" "api_server" {
  family                   = "${var.project_name}-api-server"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_server_cpu
  memory                   = var.api_server_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "airflow-api-server"
      image = "${aws_ecr_repository.airflow.repository_url}:latest"
      command = ["api-server"]

      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "AIRFLOW__CORE__EXECUTOR", value = "LocalExecutor" },
        { name = "AIRFLOW__CORE__LOAD_EXAMPLES", value = "false" },
        { name = "PYTHONPATH", value = "/opt/airflow" },
        { name = "AIRFLOW__CORE__PARALLELISM", value = "8" },
        { name = "AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG", value = "4" },
        { name = "AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG", value = "2" },
        { name = "AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL", value = "30" },
        { name = "AIRFLOW__WEBSERVER__EXPOSE_CONFIG", value = "false" },
        { name = "AIRFLOW__CORE__EXECUTION_API_SERVER_URL", value = "http://localhost:8080/execution/" },
        { name = "RAW_BUCKET", value = "devworld-raw" },
        { name = "LAKE_BUCKET", value = "devworld-lake" },
        { name = "STORAGE_REGION", value = var.storage_region },
        { name = "S3_USE_SSL", value = "true" },
        { name = "DUCKLAKE_DATA_PATH", value = "s3://devworld-lake/" },
        { name = "OLLAMA_MODEL", value = "qwen3.5:397b" },
        { name = "DB_NAME", value = "app_db" },
        { name = "DB_USER", value = var.db_username },
      ]

      secrets = [
        {
          name      = "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"
          valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:connection_string::"
        },
        {
          name      = "AIRFLOW__WEBSERVER__SECRET_KEY"
          valueFrom = "${aws_secretsmanager_secret.airflow_secret_key.arn}"
        },
        {
          name      = "AIRFLOW__CORE__FERNET_KEY"
          valueFrom = "${aws_secretsmanager_secret.fernet_key.arn}"
        },
        {
          name      = "GITHUB_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.github_token.arn}"
        },
        {
          name      = "OLLAMA_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.ollama_api_key.arn}"
        },
        {
          name      = "STORAGE_ACCESS_KEY"
          valueFrom = "${aws_secretsmanager_secret.r2_credentials.arn}:access_key_id::"
        },
        {
          name      = "STORAGE_SECRET_KEY"
          valueFrom = "${aws_secretsmanager_secret.r2_credentials.arn}:secret_access_key::"
        },
        {
          name      = "STORAGE_ENDPOINT_URL"
          valueFrom = "${aws_secretsmanager_secret.r2_credentials.arn}:endpoint::"
        },
        {
          name      = "DB_HOST"
          valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:host::"
        },
        {
          name      = "DB_PORT"
          valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:port::"
        },
        {
          name      = "DB_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:password::"
        },
        {
          name      = "DUCKLAKE_CATALOG_URL"
          valueFrom = "${aws_secretsmanager_secret.ducklake_catalog_url.arn}"
        },
        {
          name      = "APP_DB_URL"
          valueFrom = "${aws_secretsmanager_secret.app_db_url.arn}"
        },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.airflow.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api-server"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-api-server"
  }
}

# Airflow Scheduler Task Definition
resource "aws_ecs_task_definition" "scheduler" {
  family                   = "${var.project_name}-scheduler"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.scheduler_cpu
  memory                   = var.scheduler_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "airflow-scheduler"
      image = "${aws_ecr_repository.airflow.repository_url}:latest"
      command = ["scheduler"]

      environment = [
        { name = "AIRFLOW__CORE__EXECUTOR", value = "LocalExecutor" },
        { name = "AIRFLOW__CORE__LOAD_EXAMPLES", value = "false" },
        { name = "PYTHONPATH", value = "/opt/airflow" },
        { name = "AIRFLOW__CORE__PARALLELISM", value = "8" },
        { name = "AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG", value = "4" },
        { name = "AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG", value = "2" },
        { name = "AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL", value = "30" },
        { name = "AIRFLOW__WEBSERVER__EXPOSE_CONFIG", value = "false" },
        { name = "AIRFLOW__CORE__EXECUTION_API_SERVER_URL", value = "http://localhost:8080/execution/" },
        { name = "RAW_BUCKET", value = "devworld-raw" },
        { name = "LAKE_BUCKET", value = "devworld-lake" },
        { name = "STORAGE_REGION", value = var.storage_region },
        { name = "S3_USE_SSL", value = "true" },
        { name = "DUCKLAKE_DATA_PATH", value = "s3://devworld-lake/" },
        { name = "OLLAMA_MODEL", value = "qwen3.5:397b" },
        { name = "DB_NAME", value = "app_db" },
        { name = "DB_USER", value = var.db_username },
      ]

      secrets = [
        {
          name      = "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"
          valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:connection_string::"
        },
        {
          name      = "AIRFLOW__CORE__FERNET_KEY"
          valueFrom = "${aws_secretsmanager_secret.fernet_key.arn}"
        },
        {
          name      = "GITHUB_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.github_token.arn}"
        },
        {
          name      = "OLLAMA_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.ollama_api_key.arn}"
        },
        {
          name      = "STORAGE_ACCESS_KEY"
          valueFrom = "${aws_secretsmanager_secret.r2_credentials.arn}:access_key_id::"
        },
        {
          name      = "STORAGE_SECRET_KEY"
          valueFrom = "${aws_secretsmanager_secret.r2_credentials.arn}:secret_access_key::"
        },
        {
          name      = "STORAGE_ENDPOINT_URL"
          valueFrom = "${aws_secretsmanager_secret.r2_credentials.arn}:endpoint::"
        },
        {
          name      = "DB_HOST"
          valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:host::"
        },
        {
          name      = "DB_PORT"
          valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:port::"
        },
        {
          name      = "DB_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:password::"
        },
        {
          name      = "DUCKLAKE_CATALOG_URL"
          valueFrom = "${aws_secretsmanager_secret.ducklake_catalog_url.arn}"
        },
        {
          name      = "APP_DB_URL"
          valueFrom = "${aws_secretsmanager_secret.app_db_url.arn}"
        },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.airflow.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "scheduler"
        }
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-scheduler"
  }
}

# API Server Service
resource "aws_ecs_service" "api_server" {
  name            = "${var.project_name}-api-server"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api_server.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.airflow.arn
    container_name   = "airflow-api-server"
    container_port   = 8080
  }

  depends_on = [aws_lb_listener.http]

  tags = {
    Name = "${var.project_name}-api-server-service"
  }
}

# Scheduler Service
resource "aws_ecs_service" "scheduler" {
  name            = "${var.project_name}-scheduler"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.scheduler.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  tags = {
    Name = "${var.project_name}-scheduler-service"
  }
}
