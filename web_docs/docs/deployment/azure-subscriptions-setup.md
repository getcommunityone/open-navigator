---
sidebar_position: 5
---

# Azure Subscriptions Setup

How to prepare Azure so the [`infra/azure`](https://github.com/getcommunityone/open-navigator/tree/main/infra/azure) Terraform can create and name subscriptions. You do this **once**. After it's done, subscriptions are managed by editing `subscriptions.auto.tfvars` and running `make azure-plan` / `make azure-apply` (or the CI workflow).

## What you're creating

1. An **app registration + service principal** — the non-human identity Terraform authenticates as.
2. **Federated credentials (OIDC)** on it — so GitHub Actions can authenticate **without a stored secret**.
3. A **billing-scope role assignment** — the permission that actually lets it create subscriptions.

### Recommended name

```
sp-opennav-tf-subscriptions
```

Rationale (CAF convention): `sp-` = service principal, `opennav` = org, `tf` = managed by Terraform, `subscriptions` = its job (Microsoft calls this pattern *subscription vending*). Use the same string for the app registration display name and the SP.

## Prerequisites

- **An EA, MCA, or MPA billing account.** Pay-As-You-Go **cannot** create subscriptions via API/Terraform — verify with `az billing account list -o table` (see [Azure Subscriptions Setup billing scope]).
- **Your own** account must be **Owner / Global Admin** (to create the app registration) **and** have rights on the billing scope (to delegate subscription-creation to the SP).
- **Azure CLI + Terraform installed.** Get both via the installer's opt-in infra flag:
  ```bash
  INSTALL_INFRA_TOOLS=1 ./install.sh        # Linux/macOS
  ```
  ```powershell
  $env:INSTALL_INFRA_TOOLS = "1"; .\install.ps1   # Windows
  ```
  It prefers the OS package manager (apt/dnf/brew/winget/choco) and falls back to a
  rootless install into `.venv` when sudo isn't available. Then `az login`.

## Shortcut: run the bootstrap script

Steps 1–2 (and printing every value you need) are automated. After `az login`:

```bash
./infra/azure/setup-azure.sh              # creates the SP + OIDC creds, prints values
./infra/azure/setup-azure.sh --set-github # also sets the GitHub repo Variables
```

It prints `ARM_CLIENT_ID`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` ready to paste into
`.env` — the only value you must still look up yourself is the **billing scope** (Step 3).
The manual steps below explain what it does.

## Step 1 — Create the app registration + service principal

```bash
# Create the app registration and capture its appId (client id)
APP_ID=$(az ad app create \
  --display-name "sp-opennav-tf-subscriptions" \
  --query appId -o tsv)

# Create the service principal for that app
az ad sp create --id "$APP_ID"

# Note these for later — they are NOT secrets:
echo "ARM_CLIENT_ID    = $APP_ID"
echo "ARM_TENANT_ID    = $(az account show --query tenantId -o tsv)"
```

We deliberately do **not** create a client secret here — CI uses OIDC (Step 2), and local runs can use your own `az login` (Step 4).

## Step 2 — Add federated credentials (OIDC) for GitHub Actions

This lets the CI workflow exchange a short-lived GitHub token for an Azure token — **no secret is stored anywhere**.

```bash
# Trust pushes to main
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:getcommunityone/open-navigator:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'

# Trust pull requests (so PR plans authenticate too)
az ad app federated-credential create --id "$APP_ID" --parameters '{
  "name": "github-pr",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:getcommunityone/open-navigator:pull_request",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

These subjects match the triggers in `.github/workflows/azure-subscriptions.yml` (push to `main` and `pull_request`).

## Step 3 — Grant the SP rights on the billing scope (the key step)

Subscription creation is a **billing** permission, not normal subscription RBAC — `az role assignment` does **not** do this. The exact role/path depends on your agreement:

### MCA (Microsoft Customer Agreement)

Assign the **Azure subscription creator** role on the **invoice section**:

- **Portal:** Cost Management + Billing → **Billing scopes** → your account → **Billing profiles** → **Invoice sections** → pick the section → **Access control (IAM)** → **Add** → role **Azure subscription creator** → select `sp-opennav-tf-subscriptions`.
- The invoice section's resource ID is your `TF_VAR_billing_scope_id`.

### EA (Enterprise Agreement)

Add the SP as **owner of the enrollment account** (a.k.a. *SubscriptionCreator*):

- **Portal:** Cost Management + Billing → **Billing scopes** → enrollment account → assign the SP, **or** via the EA portal (`ea.azure.com`) → Enrollment account → Add the service principal.
- Scope shape: `/providers/Microsoft.Billing/billingAccounts/<enrollmentNumber>/enrollmentAccounts/<id>`.

### MPA (Partner)

Assign on the customer scope: `/providers/Microsoft.Billing/billingAccounts/<ba>/customers/<id>`.

> See [Azure Subscriptions Setup billing scope] for the `az billing …` commands that print each scope's full resource ID — that string is what goes in `TF_VAR_billing_scope_id`.

## Step 4 — (Optional) Management Group placement

If any subscription in `subscriptions.auto.tfvars` sets `management_group_id`, also grant the SP **Management Group Contributor** on that MG (this one *is* normal RBAC):

```bash
az role assignment create \
  --assignee "$APP_ID" \
  --role "Management Group Contributor" \
  --scope "/providers/Microsoft.Management/managementGroups/<mg-id>"
```

## Step 5 — Wire the values in

### CI (GitHub Actions)

```bash
gh variable set AZURE_CLIENT_ID        --body "$APP_ID"
gh variable set AZURE_TENANT_ID        --body "$(az account show --query tenantId -o tsv)"
gh variable set AZURE_SUBSCRIPTION_ID  --body "<any-existing-sub-id-to-auth-against>"
gh secret   set AZURE_BILLING_SCOPE_ID --body "<scope-id-from-step-3>"
```

### Local (`infra/azure/.env`, gitignored)

Two options:

- **Simplest — use your own `az login`.** The azurerm provider falls back to Azure CLI auth, so locally you only need the billing scope:
  ```bash
  export TF_VAR_billing_scope_id="<scope-id-from-step-3>"
  ```
  (Your user account must itself have the Step 3 permission for this to work.)
- **Use the SP via OIDC/secret** as documented in `.env.example` if you want local runs to use the same identity as CI.

## Verify

```bash
cd infra/azure
set -a && source .env && set +a
make azure-plan        # from repo root, or: terraform plan
```

A clean plan listing the `opennav-*` subscriptions means everything is wired. Then `make azure-apply` (or merge the PR — CI applies on `main`).

## Reference

- Module + naming convention: [`infra/azure/README.md`](https://github.com/getcommunityone/open-navigator/blob/main/infra/azure/README.md)
- CI workflow: `.github/workflows/azure-subscriptions.yml`
- Microsoft docs: *Programmatically create Azure subscriptions* and *Workload identity federation*.

[Azure Subscriptions Setup billing scope]: #step-3--grant-the-sp-rights-on-the-billing-scope-the-key-step
