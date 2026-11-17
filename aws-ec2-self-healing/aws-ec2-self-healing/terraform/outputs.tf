output "instance_id" {
  value = aws_instance.web.id
}

output "web_url" {
  value = "http://${aws_instance.web.public_ip}"
}

output "lambda_function" {
  value = aws_lambda_function.recovery.function_name
}

output "sns_topic_arn" {
  value = aws_sns_topic.alarms.arn
}

output "alarms" {
  value = [
    aws_cloudwatch_metric_alarm.nginx_down.alarm_name,
    aws_cloudwatch_metric_alarm.status_check.alarm_name,
  ]
}
