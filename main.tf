# S3 Bucket for receipt storage and processing trigger
resource "aws_s3_bucket" "receipts_bucket" {
  bucket        = "receipts-processing-${random_string.bucket_suffix.result}"
  force_destroy = true
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_s3_bucket_versioning" "receipts_bucket_versioning" {
  bucket = aws_s3_bucket.receipts_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "receipts_bucket_encryption" {
  bucket = aws_s3_bucket.receipts_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "receipts_bucket_cors" {
  bucket = aws_s3_bucket.receipts_bucket.id
  depends_on = [aws_s3_bucket.receipts_bucket]

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# S3 bucket notification to trigger Lambda
resource "aws_s3_bucket_notification" "receipts_notification" {
  bucket = aws_s3_bucket.receipts_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.receipt_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "new-receipts/"
    filter_suffix       = ""
  }

  depends_on = [aws_lambda_permission.s3_invoke]
}

# DynamoDB table for storing extracted receipt data
resource "aws_dynamodb_table" "receipts" {
  name           = "Receipts"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "receipt_id"
  range_key      = "timestamp"

  attribute {
    name = "receipt_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Name = "ReceiptsTable"
  }
}

# IAM role for Lambda function
resource "aws_iam_role" "lambda_role" {
  name = "receipt-processor-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM policy for Lambda function
resource "aws_iam_role_policy" "lambda_policy" {
  name = "receipt-processor-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.receipts_bucket.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "textract:DetectDocumentText",
          "textract:AnalyzeDocument"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.receipts.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda function for receipt processing
resource "aws_lambda_function" "receipt_processor" {
  filename         = "receipt_processor.zip"
  function_name    = "receipt-processor"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300

  depends_on = [data.archive_file.lambda_zip]
}

# Create Lambda deployment package
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "receipt_processor.zip"
  source {
    content = templatefile("${path.module}/lambda_function.py", {
      dynamodb_table = aws_dynamodb_table.receipts.name
      ses_email      = var.notification_email
    })
    filename = "lambda_function.py"
  }
}

# Lambda permission for S3 to invoke the function
resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.receipt_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.receipts_bucket.arn
}

# SES email identity for notifications
resource "aws_ses_email_identity" "notification_email" {
  email = var.notification_email
}

# S3 bucket for hosting static website
resource "aws_s3_bucket" "web_interface" {
  bucket        = "receipt-upload-web-${random_string.bucket_suffix.result}"
  force_destroy = true
}

resource "aws_s3_bucket_website_configuration" "web_interface" {
  bucket = aws_s3_bucket.web_interface.id

  index_document {
    suffix = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "web_interface" {
  bucket = aws_s3_bucket.web_interface.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "web_interface" {
  bucket = aws_s3_bucket.web_interface.id
  depends_on = [aws_s3_bucket_public_access_block.web_interface]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.web_interface.arn}/*"
      }
    ]
  })
}

# Upload HTML file to S3
resource "aws_s3_object" "index_html" {
  bucket       = aws_s3_bucket.web_interface.id
  key          = "index.html"
  content      = templatefile("${path.module}/index.html", {
    bucket_name = aws_s3_bucket.receipts_bucket.bucket
    region      = var.region
  })
  content_type = "text/html"
}

resource "aws_s3_bucket_public_access_block" "receipts_bucket" {
  bucket = aws_s3_bucket.receipts_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "receipts_bucket" {
  bucket = aws_s3_bucket.receipts_bucket.id
  depends_on = [aws_s3_bucket_public_access_block.receipts_bucket]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowDirectUpload"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.receipts_bucket.arn}/new-receipts/*"
      }
    ]
  })
}

data "aws_caller_identity" "current" {}