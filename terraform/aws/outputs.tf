output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "database_url" {
  value     = "postgresql+psycopg2://${var.postgres_username}:${var.postgres_password}@${aws_db_instance.postgres.address}:5432/${var.postgres_db_name}"
  sensitive = true
}

output "redis_url" {
  value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"
}

output "helm_env_snippet" {
  value = <<-EOT
    DATABASE_URL=postgresql+psycopg2://${var.postgres_username}:<password>@${aws_db_instance.postgres.address}:5432/${var.postgres_db_name}
    REDIS_URL=redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0
    QDRANT_URL=${var.qdrant_url}
    AUTH_DISABLED=false
    RUN_STORE_BACKEND=redis
    WORKFLOW_MEMORY_BACKEND=redis
    OBJECT_STORAGE_BACKEND=s3
  EOT
}
