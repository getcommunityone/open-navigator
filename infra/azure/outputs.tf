output "subscriptions" {
  description = "Created subscriptions keyed by logical name: display name, subscription_id, and tenant."
  value = {
    for key, sub in azurerm_subscription.this : key => {
      name            = sub.subscription_name
      subscription_id = sub.subscription_id
      tenant_id       = sub.tenant_id
      workload        = sub.workload
    }
  }
}

output "subscription_ids" {
  description = "Map of logical name -> subscription GUID, handy for downstream provider aliases."
  value       = { for key, sub in azurerm_subscription.this : key => sub.subscription_id }
}

output "budget" {
  description = "The cost-alert budget, if configured."
  value = length(azurerm_consumption_budget_subscription.this) == 0 ? null : {
    name       = azurerm_consumption_budget_subscription.this[0].name
    amount_usd = azurerm_consumption_budget_subscription.this[0].amount
    thresholds = var.subscription_budget.thresholds
  }
}

output "databricks_workspace_url" {
  description = "Databricks workspace URL, if managed by Terraform."
  value       = length(azurerm_databricks_workspace.this) == 0 ? null : "https://${azurerm_databricks_workspace.this[0].workspace_url}"
}
