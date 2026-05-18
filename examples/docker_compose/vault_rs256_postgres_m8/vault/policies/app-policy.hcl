# Read-only policy for the app secrets path.
# Reference for production hardening — assign this policy to a scoped app token
# instead of using the root dev token.
#
# Production steps:
#   vault policy write app-read /vault/policies/app-policy.hcl
#   APP_TOKEN=$(vault token create -policy=app-read -period=24h -format=json | jq -r .auth.client_token)
#   # Store APP_TOKEN as a Docker secret or in Vault agent config.

path "secret/data/app" {
  capabilities = ["read"]
}

path "secret/metadata/app" {
  capabilities = ["read", "list"]
}
