locals {
  # Final display name + alias: "<org_prefix>-<key>", e.g. "opennav-platform-management".
  subscription_names = {
    for key, cfg in var.subscriptions : key => "${var.org_prefix}-${key}"
  }

  # Only the subscriptions that requested a management-group placement.
  mg_associations = {
    for key, cfg in var.subscriptions : key => cfg.management_group_id
    if cfg.management_group_id != null
  }
}

resource "azurerm_subscription" "this" {
  for_each = var.subscriptions

  # alias is the immutable Terraform identity; subscription_name is the display name.
  alias             = local.subscription_names[each.key]
  subscription_name = local.subscription_names[each.key]
  billing_scope_id  = var.billing_scope_id
  workload          = each.value.workload

  tags = merge(
    var.common_tags,
    { environment = each.key },
    each.value.tags,
  )
}

resource "azurerm_management_group_subscription_association" "this" {
  for_each = local.mg_associations

  management_group_id = each.value
  subscription_id     = "/subscriptions/${azurerm_subscription.this[each.key].subscription_id}"
}
