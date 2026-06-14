# Azure subscriptions (Terraform)

Creates and names Azure subscriptions data-driven from a single map, following the
Cloud Adoption Framework (CAF) / Azure Landing Zones conventions. **No secrets live
in any `.tf` or `.tfvars` file** — all credentials are read from `.env` (ARM_* env vars).

## Naming convention

```
<org_prefix>-<landing-zone | environment>
```

| Subscription          | Purpose                                              |
| --------------------- | ---------------------------------------------------- |
| `opennav-platform-management`   | Logging, monitoring, automation (platform)  |
| `opennav-platform-connectivity` | Hub networking, DNS, firewall (platform)    |
| `opennav-platform-identity`     | Domain controllers / identity (platform)    |
| `opennav-prod`        | Production application landing zone                  |
| `opennav-nonprod`     | Dev/Test/Staging application landing zone (DevTest)  |
| `opennav-sandbox`     | Throwaway experimentation (DevTest)                  |

Rules: lowercase, hyphen-separated, env/zone always last so names sort and read
predictably. The map **key** in [`subscriptions.auto.tfvars`](subscriptions.auto.tfvars)
is the segment after `org_prefix`; add/remove/rename subscriptions by editing that map
(reviewed via PR) — nothing else changes.

## What's committed vs. loaded from `.env`

| Concern | Where | In git? |
| --- | --- | --- |
| Subscription names, topology, tags | `subscriptions.auto.tfvars` | ✅ yes (reviewable config) |
| Azure credentials (`ARM_*`) | `.env` | ❌ no (gitignored) |
| Billing-account scope (`TF_VAR_billing_scope_id`) | `.env` / CI secret | ❌ no |
| State, `*.tfstate`, real `*.tfvars` | local / remote backend | ❌ no |

No `.tf` or committed `.tfvars` file contains a secret.

## Prerequisites

- An **EA, MCA, or MPA** billing account. Pay-As-You-Go **cannot** create
  subscriptions via API/Terraform.
- A service principal with rights on the **billing scope** (Owner on the MCA invoice
  section / EA enrollment account), and `Management Group Contributor` if you set
  `management_group_id`.
- Terraform >= 1.6, azurerm provider ~> 4.0.

## Usage

```bash
cd infra/azure

# 1. credentials + billing scope (gitignored) — NEVER commit
cp .env.example .env && $EDITOR .env

# 2. (optional) adjust names/topology in subscriptions.auto.tfvars (committed)

# 3. run — via make (sources .env for you) ...
make azure-init     # from repo root
make azure-plan
make azure-apply

# ... or directly
set -a && source .env && set +a
terraform init && terraform plan && terraform apply
```

Find your billing scope for `TF_VAR_billing_scope_id` in `.env`:

```bash
az billing account list -o table
az billing profile list --account-name <ba> -o table
az billing invoice-section list --account-name <ba> --profile-name <bp> -o table
```

## CI/CD (GitHub Actions, OIDC — no stored secret)

[`.github/workflows/azure-subscriptions.yml`](../../.github/workflows/azure-subscriptions.yml)
plans on PRs touching `infra/azure/**` and applies on push to `main`. It authenticates
via **workload-identity federation** (OIDC), so there is no client secret in GitHub.
Configure once:

- A **federated credential** on the Azure service principal trusting this repo
  (`repo:getcommunityone/open-navigator:ref:refs/heads/main` and `:pull_request`).
- Repository **Variables**: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- Repository **Secret**: `AZURE_BILLING_SCOPE_ID`.

## Notes

- `alias` on `azurerm_subscription` is the immutable Terraform identity; renaming the
  display name is allowed, but changing a map **key** destroys/recreates the alias.
- Cancelling a subscription via `terraform destroy` only **cancels** it (Azure
  retains it ~90 days); it is not immediately deleted.
- Prefer **OIDC** (Option B in `.env.example`) over a client secret in CI.
- Promote state to the remote `azurerm` backend (commented in `versions.tf`) before
  collaborating — the backend reads the same ARM_* env vars.
