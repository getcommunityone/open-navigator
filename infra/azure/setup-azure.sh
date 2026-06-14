#!/usr/bin/env bash
#
# One-time Azure bootstrap for the infra/azure subscriptions Terraform.
#
# Creates (idempotently):
#   - app registration + service principal "sp-opennav-tf-subscriptions"
#   - GitHub OIDC federated credentials (main + pull_request) so CI needs no secret
# Then prints the exact values for `gh variable/secret set` and infra/azure/.env.
#
# It does NOT assign the billing-scope role (that step is agreement-specific and
# best done in the portal) and never creates a client secret.
#
# Usage:
#   az login
#   ./infra/azure/setup-azure.sh                 # create + print values
#   ./infra/azure/setup-azure.sh --set-github    # also run `gh variable set ...`
#
set -euo pipefail

REPO="getcommunityone/open-navigator"
SP_NAME="sp-opennav-tf-subscriptions"
ISSUER="https://token.actions.githubusercontent.com"
AUDIENCE="api://AzureADTokenExchange"
SET_GITHUB=0
[ "${1:-}" = "--set-github" ] && SET_GITHUB=1

command -v az >/dev/null || { echo "❌ az not found. Install: INSTALL_INFRA_TOOLS=1 ./install.sh"; exit 1; }
az account show >/dev/null 2>&1 || { echo "❌ Not logged in. Run: az login"; exit 1; }

TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "Tenant:        $TENANT_ID"
echo "Auth subscription: $SUBSCRIPTION_ID"
echo ""

# --- App registration (idempotent by display name) --------------------------------
APP_ID=$(az ad app list --display-name "$SP_NAME" --query "[0].appId" -o tsv)
if [ -z "$APP_ID" ] || [ "$APP_ID" = "null" ]; then
    echo "Creating app registration '$SP_NAME'..."
    APP_ID=$(az ad app create --display-name "$SP_NAME" --query appId -o tsv)
else
    echo "✓ App registration already exists: $APP_ID"
fi

# --- Service principal (idempotent) -----------------------------------------------
if ! az ad sp show --id "$APP_ID" >/dev/null 2>&1; then
    echo "Creating service principal..."
    az ad sp create --id "$APP_ID" >/dev/null
else
    echo "✓ Service principal already exists"
fi

# --- Federated credentials for GitHub OIDC (idempotent by name) -------------------
ensure_fic() {
    local name="$1" subject="$2"
    if az ad app federated-credential list --id "$APP_ID" --query "[?name=='$name']" -o tsv | grep -q .; then
        echo "✓ Federated credential '$name' already exists"
    else
        echo "Adding federated credential '$name' ($subject)..."
        az ad app federated-credential create --id "$APP_ID" --parameters "{
            \"name\": \"$name\",
            \"issuer\": \"$ISSUER\",
            \"subject\": \"$subject\",
            \"audiences\": [\"$AUDIENCE\"]
        }" >/dev/null
    fi
}
ensure_fic "github-main" "repo:${REPO}:ref:refs/heads/main"
ensure_fic "github-pr"   "repo:${REPO}:pull_request"

echo ""
echo "=================================================================="
echo "✅ Service principal ready."
echo "=================================================================="
echo ""
echo "GitHub Actions — repository Variables + one Secret:"
echo "  gh variable set AZURE_CLIENT_ID       --repo $REPO --body \"$APP_ID\""
echo "  gh variable set AZURE_TENANT_ID       --repo $REPO --body \"$TENANT_ID\""
echo "  gh variable set AZURE_SUBSCRIPTION_ID --repo $REPO --body \"$SUBSCRIPTION_ID\""
echo "  gh secret   set AZURE_BILLING_SCOPE_ID --repo $REPO --body \"<your-billing-scope-id>\""
echo ""
echo "Local infra/azure/.env (for non-OIDC / SP runs):"
echo "  export ARM_CLIENT_ID=\"$APP_ID\""
echo "  export ARM_TENANT_ID=\"$TENANT_ID\""
echo "  export ARM_SUBSCRIPTION_ID=\"$SUBSCRIPTION_ID\""
echo "  export TF_VAR_billing_scope_id=\"<your-billing-scope-id>\""
echo ""
echo "⚠ STILL REQUIRED (manual): grant '$SP_NAME' the subscription-creator role on"
echo "  your billing scope. See web_docs/docs/deployment/azure-subscriptions-setup.md §Step 3."
echo "  Find the scope id: az billing account list -o table"

if [ "$SET_GITHUB" = "1" ]; then
    echo ""
    if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
        echo "Setting GitHub Variables (billing-scope Secret left to you)..."
        gh variable set AZURE_CLIENT_ID       --repo "$REPO" --body "$APP_ID"
        gh variable set AZURE_TENANT_ID       --repo "$REPO" --body "$TENANT_ID"
        gh variable set AZURE_SUBSCRIPTION_ID --repo "$REPO" --body "$SUBSCRIPTION_ID"
        echo "✓ Variables set. Now: gh secret set AZURE_BILLING_SCOPE_ID --repo $REPO --body \"<scope>\""
    else
        echo "⚠ --set-github requested but gh isn't installed/authenticated; run the commands above manually."
    fi
fi
