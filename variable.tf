variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "notification_email" {
  description = "Email address for receipt processing notifications"
  type        = string
  default     = ""
}