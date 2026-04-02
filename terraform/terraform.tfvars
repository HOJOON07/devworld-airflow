aws_region  = "ap-northeast-2"
environment = "prod"

# VPC
vpc_cidr             = "10.0.0.0/16"
availability_zones   = ["ap-northeast-2a", "ap-northeast-2c"]
public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]

# ECS
api_server_cpu    = 512
api_server_memory = 1024
scheduler_cpu     = 512
scheduler_memory  = 1024

# RDS
db_instance_class    = "db.t3.micro"
db_allocated_storage = 20
db_name              = "airflow_db"
db_username          = "devworld"

# CloudWatch 알람 이메일 (비워두면 알림 비활성)
alarm_email = ""

# ACM 인증서 ARN (HTTPS)
acm_certificate_arn = "arn:aws:acm:ap-northeast-2:845687758046:certificate/78a2c2f4-b013-437b-8077-ec6b8243dbaa"

# NestJS API ECS
nestjs_api_cpu    = 512
nestjs_api_memory = 1024
