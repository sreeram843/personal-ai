# Azure skeleton — extend before production use

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Wire: AKS, PostgreSQL Flexible Server, Azure Cache for Redis, Key Vault.
# See terraform/aws for the reference layout.

output "next_steps" {
  value = "Complete AKS + Postgres modules, then deploy helm/personal-ai with Key Vault secret refs."
}
