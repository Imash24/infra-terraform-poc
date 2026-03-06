variable "environment" {
  type = string
}

resource "aws_rds_cluster" "main" {
  cluster_identifier  = "finops-poc-${var.environment}"
  engine              = "aurora-postgresql"
  engine_version      = "15.4"
  database_name       = "appdb"
  master_username     = "admin"
  master_password     = "change_me_in_production"
  skip_final_snapshot = true

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_rds_cluster_instance" "main" {
  count              = 2
  identifier         = "finops-poc-${var.environment}-${count.index}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.r6g.large"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
