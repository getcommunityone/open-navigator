# Optional Azure Databricks workspace + its resource group, gated on the
# databricks_workspace variable. Resources land in the provider's default
# subscription (ARM_SUBSCRIPTION_ID = opennav-prod).
#
# CURRENTLY INACTIVE (variable defaults to null). The live workspace
# dbw-opennav-prod-eastus-001 was created in the portal on the 14-day TRIAL sku and
# is managed MANUALLY for now — same pattern as the subscription itself. To let
# Terraform manage it, set databricks_workspace in subscriptions.auto.tfvars and
# import the existing resources (see README), ideally after upgrading off trial.

resource "azurerm_resource_group" "databricks" {
  count    = var.databricks_workspace == null ? 0 : 1
  name     = var.databricks_workspace.resource_group_name
  location = var.databricks_workspace.location
  tags     = var.common_tags
}

resource "azurerm_databricks_workspace" "this" {
  count               = var.databricks_workspace == null ? 0 : 1
  name                = var.databricks_workspace.name
  resource_group_name = azurerm_resource_group.databricks[0].name
  location            = var.databricks_workspace.location
  sku                 = var.databricks_workspace.sku

  # Set to the existing managed RG name when importing, else Azure generates one.
  managed_resource_group_name = var.databricks_workspace.managed_resource_group_name

  custom_parameters {
    no_public_ip = var.databricks_workspace.no_public_ip
  }

  tags = var.common_tags
}
