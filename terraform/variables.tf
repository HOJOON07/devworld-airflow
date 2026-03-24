variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-2"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "devworld"
}

# VPC
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2c"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

# ECS
variable "webserver_cpu" {
  description = "CPU units for Airflow webserver (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "webserver_memory" {
  description = "Memory in MiB for Airflow webserver"
  type        = number
  default     = 1024
}

variable "scheduler_cpu" {
  description = "CPU units for Airflow scheduler (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "scheduler_memory" {
  description = "Memory in MiB for Airflow scheduler"
  type        = number
  default     = 1024
}

# RDS
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB for RDS"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Default database name"
  type        = string
  default     = "airflow_db"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "devworld"
}
