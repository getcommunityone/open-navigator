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
