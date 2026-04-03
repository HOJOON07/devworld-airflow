# ECS Task Execution Role (pulls images, writes logs, reads secrets)
resource "aws_iam_role" "ecs_execution" {
  name = "${var.project_name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ecs-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution_base" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_policy" "ecs_execution_secrets" {
  name        = "${var.project_name}-ecs-execution-secrets"
  description = "Allow ECS execution role to read secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.db_credentials.arn,
          aws_secretsmanager_secret.airflow_secret_key.arn,
          aws_secretsmanager_secret.airflow_jwt_secret.arn,
          aws_secretsmanager_secret.r2_credentials.arn,
          aws_secretsmanager_secret.fernet_key.arn,
          aws_secretsmanager_secret.github_token.arn,
          aws_secretsmanager_secret.ollama_api_key.arn,
          aws_secretsmanager_secret.ducklake_catalog_url.arn,
          aws_secretsmanager_secret.app_db_url.arn,
          aws_secretsmanager_secret.nestjs_platform_db.arn,
          aws_secretsmanager_secret.nestjs_app_db.arn,
          aws_secretsmanager_secret.nestjs_jwt_secrets.arn,
          aws_secretsmanager_secret.nestjs_github_oauth.arn,
          aws_secretsmanager_secret.nestjs_encryption_key.arn,
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_secrets" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.ecs_execution_secrets.arn
}

# ECS Task Role (application-level permissions)
resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ecs-task-role"
  }
}

resource "aws_iam_policy" "ecs_task_secrets" {
  name        = "${var.project_name}-ecs-task-secrets"
  description = "Allow ECS tasks to read secrets at runtime"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.db_credentials.arn,
          aws_secretsmanager_secret.r2_credentials.arn,
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_secrets" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_task_secrets.arn
}

resource "aws_iam_policy" "ecs_task_ssm" {
  name        = "${var.project_name}-ecs-task-ssm"
  description = "Allow ECS Exec via SSM"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel",
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_ssm" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_task_ssm.arn
}

resource "aws_iam_policy" "ecs_task_logs" {
  name        = "${var.project_name}-ecs-task-logs"
  description = "Allow Airflow tasks to write remote logs to CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:GetLogEvents",
        ]
        Resource = [
          "${aws_cloudwatch_log_group.airflow_task_logs.arn}:*",
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_logs" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_task_logs.arn
}
