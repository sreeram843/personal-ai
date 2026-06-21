resource "aws_secretsmanager_secret" "app" {
  name = "${var.project_name}/app"
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DATABASE_URL = "postgresql+psycopg2://${var.postgres_username}:${var.postgres_password}@${aws_db_instance.postgres.address}:5432/${var.postgres_db_name}"
    REDIS_URL    = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"
    JWT_SECRET   = var.jwt_secret
    QDRANT_URL   = var.qdrant_url
    QDRANT_API_KEY = var.qdrant_api_key
  })
}

output "secrets_manager_arn" {
  value = aws_secretsmanager_secret.app.arn
}
