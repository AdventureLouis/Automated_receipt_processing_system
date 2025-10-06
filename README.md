# AWS Automated Receipt Processing System

This Terraform project creates a modern, automated receipt processing system that extracts structured data from receipts and stores it for audit and record-keeping purposes.


## Video Demo

https://github.com/user-attachments/assets/01922108-9320-4e31-a013-57f0f3cac5f1

## Architecture Components

- **S3 Bucket**: Secure storage for original receipts with automatic processing triggers
- **DynamoDB Table**: Structured storage for extracted receipt data
- **Lambda Function**: Automated processing using Amazon Textract
- **Amazon Textract**: AI-powered text extraction from receipts
- **Amazon SES**: Email notifications for processed receipts
- **IAM Roles**: Minimal required permissions for secure operation

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Terraform installed (>= 1.0)
3. Valid email address for SES notifications

## Deployment Steps

1. **Configure Variables**:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your email address
   ```

2. **Initialize Terraform**:
   ```bash
   terraform init
   ```

3. **Plan Deployment**:
   ```bash
   terraform plan
   ```

4. **Deploy Infrastructure**:
   ```bash
   terraform apply
   ```

5. **Verify SES Email**:
   - Check your email for SES verification message
   - Click the verification link

## Usage

1. **Upload Receipts**:
   - **Web Interface**: Use the provided web URL to upload receipts via browser
   - **Direct S3**: Upload PDF, JPG, or PNG receipts to: `s3://[bucket-name]/new-receipts/`
   - Processing will trigger automatically

2. **View Processed Data**:
   - Check DynamoDB table "Receipts" for extracted data
   - Receive email notifications for each processed receipt

3. **Query Receipt Data**:
   - Use AWS Console or SDK to query the DynamoDB table
   - Filter by receipt_id, timestamp, or other attributes

## Supported File Types

- PDF documents
- JPEG/JPG images  
- PNG images

## Security Features

- S3 bucket encryption enabled
- IAM roles with minimal required permissions
- Versioning enabled for receipt storage
- Secure data transmission and storage

## Cost Optimization

- DynamoDB configured with pay-per-request billing
- Lambda function with appropriate timeout settings
- S3 lifecycle policies can be added for long-term archival

## Cleanup

To destroy all resources:
```bash
terraform destroy
```


## Architecture
![Architecture](https://github.com/user-attachments/assets/4e25b609-7af8-48e4-a1e4-0ebad7cb3600)






