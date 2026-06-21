# Terraform — Personal AI cloud infrastructure

Minimal Terraform layouts for deploying Personal AI on managed Kubernetes with external Postgres, Redis, and Qdrant.

| Path | Cloud | Status |
|------|-------|--------|
| [aws/](aws/) | Amazon EKS + RDS + ElastiCache | **Documented end-to-end path** |
| [gcp/](gcp/) | GKE + Cloud SQL + Memorystore | Skeleton |
| [azure/](azure/) | AKS + Flexible Server + Azure Cache | Skeleton |

## Prerequisites

- Terraform >= 1.5
- Cloud CLI authenticated (`aws`, `gcloud`, or `az`)
- Container image published to a registry reachable from the cluster
- Qdrant Cloud cluster URL + API key (or self-hosted Qdrant)

## AWS quick start (recommended)

See [docs/cloud-deploy-aws.md](../docs/cloud-deploy-aws.md) for the full walkthrough.

```bash
cd terraform/aws
cp terraform.tfvars.example terraform.tfvars
# Edit vpc_cidr, db_password, jwt_secret, qdrant_url, image tag

terraform init
terraform plan
terraform apply
```

After apply:

1. Configure `kubectl` with the output `kubeconfig_command`
2. Install the Helm chart with env vars from `helm_env_snippet` output
3. Point Grafana at Prometheus and import `monitoring/grafana/dashboards/live-data.json`

## Secrets

Never commit `terraform.tfvars`. Production should use:

- **AWS** — Secrets Manager + External Secrets Operator (see `aws/secrets.tf`)
- **GCP** — Secret Manager (see `gcp/variables.tf` comments)
- **Azure** — Key Vault (see `azure/variables.tf` comments)

## State

Each environment folder is independent. Use a remote backend (S3 + DynamoDB, GCS, or Azure Storage) before team use.
