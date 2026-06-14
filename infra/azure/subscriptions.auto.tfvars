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

# Minimal setup: ONE subscription. An empty subscription costs nothing — you're
# billed only for resources you deploy inside it — so a single sub is the simplest
# and cheapest starting point. Map key = name after org_prefix ("prod" -> "opennav-prod").
#
# To add more later, just add a line (each is free until you deploy into it), e.g.:
#   "sandbox" = { workload = "DevTest" }   # DevTest = discounted dev/test pricing
subscriptions = {
  "prod" = { workload = "Production" }
}
