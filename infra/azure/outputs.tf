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
