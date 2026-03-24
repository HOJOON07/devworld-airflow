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

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  tags = {
    Name = "${var.project_name}-rds-storage-alarm"
  }
}

# ECS Webserver Running Task Count Alarm
resource "aws_cloudwatch_metric_alarm" "ecs_webserver_running" {
  alarm_name          = "${var.project_name}-webserver-not-running"
  alarm_description   = "Airflow webserver has no running tasks"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RunningTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 60
  statistic           = "Average"
  threshold           = 1

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.webserver.name
  }

  tags = {
    Name = "${var.project_name}-webserver-running-alarm"
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

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.scheduler.name
  }

  tags = {
    Name = "${var.project_name}-scheduler-running-alarm"
  }
}
