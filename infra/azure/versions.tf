terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  # Remote state recommended once you have a storage account.
  # Auth for the backend ALSO comes from ARM_* env vars (no secrets here).
  # backend "azurerm" {
  #   resource_group_name  = "rg-tfstate"
  #   storage_account_name = "opennavtfstate"
  #   container_name       = "tfstate"
  #   key                  = "subscriptions.tfstate"
  # }
}
