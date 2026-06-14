variable "org_prefix" {
  description = "Short org/company code that prefixes every subscription name (CAF convention). e.g. \"opennav\"."
  type        = string
  default     = "opennav"

  validation {
    condition     = can(regex("^[a-z0-9]{2,10}$", var.org_prefix))
    error_message = "org_prefix must be 2-10 lowercase alphanumeric characters."
  }
}

variable "billing_scope_id" {
  description = <<-EOT
    Billing scope under which subscriptions are created. Format depends on agreement type:
      MCA: /providers/Microsoft.Billing/billingAccounts/{ba}/billingProfiles/{bp}/invoiceSections/{is}
      EA : /providers/Microsoft.Billing/billingAccounts/{ba}/enrollmentAccounts/{ea}
      MPA: /providers/Microsoft.Billing/billingAccounts/{ba}/customers/{customer}
    NOTE: Pay-As-You-Go subscriptions cannot be created via Terraform (no billing API).
  EOT
  type        = string

  validation {
    condition     = startswith(var.billing_scope_id, "/providers/Microsoft.Billing/billingAccounts/")
    error_message = "billing_scope_id must start with /providers/Microsoft.Billing/billingAccounts/."
  }
}

variable "common_tags" {
  description = "Tags applied to every subscription, merged with per-subscription tags."
  type        = map(string)
  default = {
    managed_by = "terraform"
    project    = "open-navigator"
  }
}

variable "subscriptions" {
  description = <<-EOT
    Map of subscriptions to create. The MAP KEY is the name segment appended to
    org_prefix to form the subscription display name (e.g. key "prod" -> "opennav-prod").
    Keep keys kebab-case so names read as <org>-<env|landing-zone>.
  EOT
  type = map(object({
    # Azure billing workload class: "Production" or "DevTest" (DevTest gets dev pricing).
    workload = optional(string, "Production")
    # Optional management group to associate the subscription with after creation.
    management_group_id = optional(string)
    # Per-subscription tags, merged over common_tags.
    tags = optional(map(string), {})
  }))

  validation {
    condition     = alltrue([for k, _ in var.subscriptions : can(regex("^[a-z0-9-]{2,40}$", k))])
    error_message = "Each subscription key must be 2-40 chars of lowercase letters, digits, or hyphens."
  }

  validation {
    condition     = alltrue([for _, v in var.subscriptions : contains(["Production", "DevTest"], v.workload)])
    error_message = "workload must be either \"Production\" or \"DevTest\"."
  }
}

variable "subscription_budget" {
  description = <<-EOT
    Optional monthly cost-ALERT budget on an EXISTING subscription (referenced by
    GUID, so it works even for subscriptions this module doesn't manage). This is an
    ALERT that emails when crossed — NOT a hard spending cap. null disables it.
  EOT
  type = object({
    name            = string                            # budget name, e.g. "opennav-prod-monthly"
    subscription_id = string                            # subscription GUID to watch (no /subscriptions/ prefix)
    amount          = number                            # monthly budget in USD
    start_date      = string                            # first day of a month, ISO8601 e.g. "2026-06-01T00:00:00Z"
    contact_emails  = list(string)                      # who gets the alert emails
    thresholds      = optional(list(number), [80, 100]) # % of amount that trigger alerts
  })
  default = null

  validation {
    condition     = var.subscription_budget == null ? true : var.subscription_budget.amount > 0
    error_message = "subscription_budget.amount must be greater than 0."
  }
}
