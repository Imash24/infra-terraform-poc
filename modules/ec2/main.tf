variable "environment" {
  type = string
}

resource "aws_instance" "app_server" {
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "t3.medium"

  tags = {
    Name        = "app-server-${var.environment}"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
