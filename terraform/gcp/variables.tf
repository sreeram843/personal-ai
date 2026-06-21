variable "gcp_project_id" { type = string }
variable "gcp_region" { type = string default = "us-central1" }
variable "qdrant_url" { type = string }
# Store JWT_SECRET and DB passwords in Secret Manager — never in tfvars in CI.
