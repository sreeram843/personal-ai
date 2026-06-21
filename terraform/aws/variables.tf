variable "project_name" {
  type    = string
  default = "personal-ai"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "single_nat_gateway" {
  type    = bool
  default = true
}

variable "eks_cluster_version" {
  type    = string
  default = "1.29"
}

variable "eks_node_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}

variable "eks_node_desired_size" {
  type    = number
  default = 2
}

variable "eks_node_max_size" {
  type    = number
  default = 4
}

variable "postgres_engine_version" {
  type    = string
  default = "16.3"
}

variable "postgres_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "postgres_db_name" {
  type    = string
  default = "personal_ai"
}

variable "postgres_username" {
  type    = string
  default = "postgres"
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.small"
}

variable "jwt_secret" {
  type      = string
  sensitive = true
}

variable "qdrant_url" {
  type = string
}

variable "qdrant_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "container_image" {
  type    = string
  default = "personal-ai:latest"
}
