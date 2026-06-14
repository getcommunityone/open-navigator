# The azurerm provider reads ALL credentials from environment variables:
#   ARM_TENANT_ID, ARM_SUBSCRIPTION_ID, ARM_CLIENT_ID, ARM_CLIENT_SECRET
# (or, preferred, OIDC: ARM_USE_OIDC=true with ARM_OIDC_TOKEN/federated creds).
#
# => No secrets are ever written into .tf files or .tfvars.
# Populate them in .env (see .env.example) and `source` it before running.
provider "azurerm" {
  features {}

  # Allow the provider to start even if no resource providers are registered
  # on the bootstrap subscription used purely for authentication.
  resource_provider_registrations = "none"
}
