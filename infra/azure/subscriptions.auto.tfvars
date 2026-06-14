# Version-controlled subscription naming + topology (NO secrets here).
# Auto-loaded by terraform (*.auto.tfvars). Edit this map to add/remove/rename
# subscriptions — review it via PR. Credentials and the billing-account identifier
# come from .env (ARM_* and TF_VAR_billing_scope_id), never this file.

org_prefix = "opennav"

common_tags = {
  managed_by  = "terraform"
  project     = "open-navigator"
  cost_center = "engineering"
  owner       = "johncbowyer"
}

# Subscriptions Terraform should CREATE + manage. Currently EMPTY on purpose:
#
# `opennav-prod` (id 2478d3f4-1db6-4832-88f8-c13f68d6c818) already exists — it's the
# tenant's original subscription, renamed to follow the CAF convention, and is managed
# MANUALLY (not imported). It is deliberately NOT listed here: azurerm_subscription
# can't safely adopt a pre-existing subscription (billing_scope_id isn't readable on
# import → Terraform would try to force-replace it). Listing "prod" here would make
# `apply` create a SECOND, duplicate opennav-prod.
#
# Programmatic creation is also currently blocked by Azure's account-eligibility gate
# (PurchaseNeedsReview → https://aka.ms/AccountReview).
#
# Once eligibility clears, add NEW subscriptions here (each is free until you deploy
# into it). Map key = name after org_prefix, e.g. "sandbox" -> "opennav-sandbox":
#   "sandbox" = { workload = "DevTest" }   # DevTest = discounted dev/test pricing
subscriptions = {}

# Monthly cost-ALERT budget on opennav-prod (an ALERT, not a hard cap — it emails
# when crossed; it does not stop spending). Emails fire at 80% ($320) and 100% ($400).
subscription_budget = {
  name            = "opennav-prod-monthly"
  subscription_id = "2478d3f4-1db6-4832-88f8-c13f68d6c818" # opennav-prod
  amount          = 400
  start_date      = "2026-06-01T00:00:00Z"
  contact_emails  = ["johnbowyer@getcommunityone.onmicrosoft.com"]
  thresholds      = [80, 100]
}

# Databricks workspace — INACTIVE. dbw-opennav-prod-eastus-001 was created in the
# portal on the TRIAL sku and is managed manually for now. To let Terraform manage
# it, upgrade off trial, uncomment below, then import (see README):
#   terraform import 'azurerm_resource_group.databricks[0]' /subscriptions/2478d3f4-1db6-4832-88f8-c13f68d6c818/resourceGroups/rg-opennav-prod-eastus-001
#   terraform import 'azurerm_databricks_workspace.this[0]'  /subscriptions/2478d3f4-1db6-4832-88f8-c13f68d6c818/resourceGroups/rg-opennav-prod-eastus-001/providers/Microsoft.Databricks/workspaces/dbw-opennav-prod-eastus-001
# databricks_workspace = {
#   name                        = "dbw-opennav-prod-eastus-001"
#   resource_group_name         = "rg-opennav-prod-eastus-001"
#   location                    = "eastus"
#   sku                         = "premium" # upgrade off "trial" first
#   no_public_ip                = true
#   managed_resource_group_name = "databricks-rg-dbw-opennav-prod-eastus-001-ncht62dsp66ds"
# }
