variable "environment" {
  type = string
}

resource "aws_s3_bucket" "data_lake" {
  bucket = "finops-poc-data-lake-${var.environment}"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  versioning_configuration {
    status = "Enabled"
  }
}
