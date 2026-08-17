# GCP skeleton — extend before production use

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# Wire: GKE cluster, Cloud SQL Postgres, Memorystore Redis, Secret Manager.
# See terraform/aws for the reference layout and docs/runbooks/cloud-deploy-aws.md for Helm steps.

output "next_steps" {
  value = "Complete GKE + Cloud SQL modules, then deploy helm/personal-ai with managed service URLs."
}
