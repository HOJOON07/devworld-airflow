# SNS Topic for alarm notifications (email 설정 시에만 생성)
resource "aws_sns_topic" "alarms" {
  count = var.alarm_email != "" ? 1 : 0
  name  = "${var.project_name}-alarms"

  tags = {
    Name = "${var.project_name}-alarms"
  }
}

resource "aws_sns_topic_subscription" "alarm_email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

locals {
  alarm_actions = var.alarm_email != "" ? [aws_sns_topic.alarms[0].arn] : []
}

resource "aws_cloudwatch_log_group" "airflow" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-logs"
  }
}

# RDS CPU Utilization Alarm
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.project_name}-rds-cpu-high"
  alarm_description   = "RDS CPU utilization exceeds 80%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  tags = {
    Name = "${var.project_name}-rds-cpu-alarm"
  }
}

# RDS Free Storage Alarm
resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "${var.project_name}-rds-storage-low"
  alarm_description   = "RDS free storage below 2GB"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 2000000000

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  tags = {
    Name = "${var.project_name}-rds-storage-alarm"
  }
}

# ECS API Server Running Task Count Alarm
resource "aws_cloudwatch_metric_alarm" "ecs_api_server_running" {
  alarm_name          = "${var.project_name}-api-server-not-running"
  alarm_description   = "Airflow API server has no running tasks"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 1

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.api_server.name
  }

  tags = {
    Name = "${var.project_name}-api-server-running-alarm"
  }
}

# ECS Scheduler Running Task Count Alarm
resource "aws_cloudwatch_metric_alarm" "ecs_scheduler_running" {
  alarm_name          = "${var.project_name}-scheduler-not-running"
  alarm_description   = "Airflow scheduler has no running tasks"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 1

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.scheduler.name
  }

  tags = {
    Name = "${var.project_name}-scheduler-running-alarm"
  }
}

# ─── NestJS API ───

resource "aws_cloudwatch_log_group" "nestjs_api" {
  name              = "/ecs/${var.project_name}-nestjs-api"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-nestjs-api-logs"
  }
}

resource "aws_cloudwatch_metric_alarm" "ecs_nestjs_api_running" {
  alarm_name          = "${var.project_name}-nestjs-api-not-running"
  alarm_description   = "NestJS API has no running tasks"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 1

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.nestjs_api.name
  }

  tags = {
    Name = "${var.project_name}-nestjs-api-running-alarm"
  }
}
