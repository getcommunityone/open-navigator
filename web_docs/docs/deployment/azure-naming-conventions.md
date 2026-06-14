---
sidebar_position: 6
---

# Azure Naming Conventions

We follow Microsoft's [Cloud Adoption Framework (CAF)](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming) naming and tagging guidance for all Azure resources. Consistent names make resources self-describing (type, workload, environment, region) and keep cost reports, RBAC, and automation predictable.

Our subscription naming (`opennav-prod`, etc.) already uses this convention — see [Azure Subscriptions Setup](azure-subscriptions-setup.md). This page is the standard to follow **inside** those subscriptions.

## The pattern

```
<resource-type>-<workload>-<environment>-<region>-<instance>
```

| Component | Meaning | Examples |
| --- | --- | --- |
| `resource-type` | CAF abbreviation for the resource | `rg`, `st`, `kv`, `psql` |
| `workload` | App / project short code | `opennav` |
| `environment` | Deployment stage | `prod`, `nonprod`, `sandbox` |
| `region` | Azure region short name | `eastus` |
| `instance` | Zero-padded instance number | `001` |

**Example:** a production resource group → `rg-opennav-prod-eastus-001`.

Rules: **lowercase**, hyphen-separated, segments in this fixed order. Omit a segment only when it doesn't apply (e.g. globally-unique types that forbid hyphens — see below).

## Our standard values

| Slot | Allowed values |
| --- | --- |
| Workload (`org_prefix`) | `opennav` |
| Environment | `prod`, `nonprod`, `sandbox` |
| Region | `eastus` (primary) |
| Instance | `001`, `002`, … |

These mirror the Terraform variables in [`infra/azure`](https://github.com/getcommunityone/open-navigator/tree/main/infra/azure) (`org_prefix`, the `subscriptions` map keys).

## Resource type abbreviations (CAF)

Common ones we use. Full list in the [CAF abbreviation reference](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations).

| Resource | Abbrev | Example |
| --- | --- | --- |
| Resource group | `rg` | `rg-opennav-prod-eastus-001` |
| Storage account | `st` | `stopennavprodeus001` ¹ |
| Key Vault | `kv` | `kv-opennav-prod-eus` ¹ |
| PostgreSQL flexible server | `psql` | `psql-opennav-prod-eastus-001` |
| App Service plan | `asp` | `asp-opennav-prod-eastus-001` |
| Web App / App Service | `app` | `app-opennav-prod-eastus-001` |
| Function App | `func` | `func-opennav-prod-eastus-001` |
| Container registry | `cr` | `cropennavprod001` ¹ |
| Virtual network | `vnet` | `vnet-opennav-prod-eastus-001` |
| Subnet | `snet` | `snet-opennav-prod-eastus-001` |
| Network security group | `nsg` | `nsg-opennav-prod-eastus-001` |
| Log Analytics workspace | `log` | `log-opennav-prod-eastus-001` |
| Application Insights | `appi` | `appi-opennav-prod-eastus-001` |
| Managed identity | `id` | `id-opennav-prod-eastus-001` |
| Management group | `mg` | `mg-opennav-platform` |

¹ **Globally-unique / restricted names.** Some resources have tight rules that break the standard pattern:

- **Storage account** — 3–24 chars, **lowercase letters + digits only, no hyphens**, globally unique. Use a compact form: `st` + workload + env + region-short + instance, e.g. `stopennavprodeus001`.
- **Key Vault** — 3–24 chars, globally unique; hyphens allowed but keep it short.
- **Container registry** — 5–50 chars, **alphanumeric only**, globally unique.

When hyphens aren't allowed, drop them and shorten the region (e.g. `eus` for East US) — but keep the same segment order.

## Tagging

Every resource carries these tags (the Terraform applies them via `common_tags`):

| Tag | Value |
| --- | --- |
| `managed_by` | `terraform` |
| `project` | `open-navigator` |
| `environment` | `prod` / `nonprod` / `sandbox` |
| `cost_center` | `engineering` |
| `owner` | resource owner |

Tags drive cost attribution and lifecycle policies — prefer them over encoding extra metadata into names.

## Region short names

| Region | Long | Short |
| --- | --- | --- |
| East US | `eastus` | `eus` |
| West US 2 | `westus2` | `wus2` |
| Central US | `centralus` | `cus` |

Use the long form in the standard pattern; use the short form only for hyphen-restricted names.

## References

- [CAF — Define your naming convention](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming)
- [CAF — Recommended abbreviations](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations)
- [CAF — Tagging strategy](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-tagging)
- This repo: [`infra/azure/README.md`](https://github.com/getcommunityone/open-navigator/blob/main/infra/azure/README.md)
