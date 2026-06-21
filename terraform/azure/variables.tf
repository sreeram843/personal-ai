variable "azure_location" { type = string default = "eastus" }
variable "resource_group_name" { type = string default = "personal-ai-rg" }
variable "qdrant_url" { type = string }
# Store secrets in Azure Key Vault — reference from AKS via CSI driver.
