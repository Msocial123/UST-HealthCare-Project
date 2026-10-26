output "queue_arn" {
  description = "Main queue ARN."
  value       = aws_sqs_queue.this.arn
}

output "queue_url" {
  description = "Main queue URL."
  value       = aws_sqs_queue.this.id
}

output "dlq_arn" {
  description = "Dead-letter queue ARN."
  value       = aws_sqs_queue.dlq.arn
}
