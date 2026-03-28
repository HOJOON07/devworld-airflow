resource "aws_lb" "airflow" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = {
    Name = "${var.project_name}-alb"
  }
}

resource "aws_lb_target_group" "airflow" {
  name        = "${var.project_name}-api-server-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    matcher             = "200"
  }

  tags = {
    Name = "${var.project_name}-api-server-tg"
  }
}

# HTTP → HTTPS 리다이렉트 (도메인 + ACM 인증서 설정 후 활성화)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.airflow.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = var.acm_certificate_arn != "" ? "redirect" : "forward"

    # HTTPS 미설정 시 HTTP로 직접 포워딩 (개발용)
    target_group_arn = var.acm_certificate_arn != "" ? null : aws_lb_target_group.airflow.arn

    # HTTPS 설정 시 리다이렉트
    dynamic "redirect" {
      for_each = var.acm_certificate_arn != "" ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  tags = {
    Name = "${var.project_name}-http-listener"
  }
}

# HTTPS listener (ACM 인증서 설정 시에만 생성)
resource "aws_lb_listener" "https" {
  count             = var.acm_certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.airflow.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.airflow.arn
  }

  tags = {
    Name = "${var.project_name}-https-listener"
  }
}
