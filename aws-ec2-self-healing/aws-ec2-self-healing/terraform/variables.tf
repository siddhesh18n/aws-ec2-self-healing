variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Prefix used for resource names"
  type        = string
  default     = "self-healing"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "allowed_http_cidr" {
  description = "CIDR allowed to reach NGINX on port 80"
  type        = string
  default     = "0.0.0.0/0"
}

variable "slack_webhook_url" {
  description = "Slack incoming webhook URL (stored as an SSM SecureString). Leave default to skip Slack."
  type        = string
  default     = "not-configured"
  sensitive   = true
}
