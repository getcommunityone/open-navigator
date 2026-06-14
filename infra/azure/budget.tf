# Monthly cost-ALERT budget on an existing subscription.
#
# IMPORTANT: an Azure budget is an ALERT, not a hard cap — it emails the contacts
# when spend crosses a threshold; it does NOT stop or block resources. It targets
# the subscription by GUID, so it works even though this module no longer manages
# the subscription itself (see subscriptions.auto.tfvars).
resource "azurerm_consumption_budget_subscription" "this" {
  count = var.subscription_budget == null ? 0 : 1

  name            = var.subscription_budget.name
  subscription_id = "/subscriptions/${var.subscription_budget.subscription_id}"
  amount          = var.subscription_budget.amount
  time_grain      = "Monthly"

  time_period {
    start_date = var.subscription_budget.start_date
  }

  # One actual-cost notification per threshold (e.g. 80% and 100% of amount).
  dynamic "notification" {
    for_each = toset(var.subscription_budget.thresholds)
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      threshold_type = "Actual"
      contact_emails = var.subscription_budget.contact_emails
    }
  }
}
