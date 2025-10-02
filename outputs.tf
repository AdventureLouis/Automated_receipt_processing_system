output "s3_bucket_name" {
  description = "Name of the S3 bucket for receipt storage"
  value       = aws_s3_bucket.receipts_bucket.bucket
}

output "s3_upload_path" {
  description = "S3 path where new receipts should be uploaded"
  value       = "${aws_s3_bucket.receipts_bucket.bucket}/new-receipts/"
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table storing receipt data"
  value       = aws_dynamodb_table.receipts.name
}

output "lambda_function_name" {
  description = "Name of the Lambda function processing receipts"
  value       = aws_lambda_function.receipt_processor.function_name
}

output "ses_email_identity" {
  description = "SES email identity for notifications"
  value       = aws_ses_email_identity.notification_email.email
}

output "web_interface_url" {
  description = "URL for the web-based receipt upload interface"
  value       = "http://${aws_s3_bucket.web_interface.bucket}.s3-website-${var.region}.amazonaws.com"
}