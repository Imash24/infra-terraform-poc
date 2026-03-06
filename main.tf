terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

module "s3" {
  source      = "./modules/s3"
  environment = var.environment
}

module "ec2" {
  source      = "./modules/ec2"
  environment = var.environment
}

module "rds" {
  source      = "./modules/rds"
  environment = var.environment
}
