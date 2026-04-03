# S3 Gateway Endpoint (무료) — NAT Gateway를 거치지 않고 S3에 직접 접근
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.aws_region}.s3"

  route_table_ids = [
    aws_route_table.private.id,
  ]

  tags = {
    Name = "${var.project_name}-s3-endpoint"
  }
}
