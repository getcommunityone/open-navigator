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

# Azure Landing Zones topology: platform subscriptions + per-environment app zones.
# Map key = name segment after org_prefix, e.g. "prod" -> "opennav-prod".
subscriptions = {
  # --- Platform landing zones ---
  "platform-management"   = { workload = "Production" }
  "platform-connectivity" = { workload = "Production" }
  "platform-identity"     = { workload = "Production" }

  # --- Application landing zones (open-navigator workloads) ---
  "prod" = {
    workload = "Production"
    tags     = { environment_class = "production" }
  }
  "nonprod" = {
    workload = "DevTest"
    tags     = { environment_class = "non-production" }
  }
  "sandbox" = {
    workload = "DevTest"
    tags     = { environment_class = "experimentation" }
  }
  # Add a management group once it exists:
  #   "prod" = { workload = "Production", management_group_id = "/providers/Microsoft.Management/managementGroups/mg-opennav-landingzones" }
}
