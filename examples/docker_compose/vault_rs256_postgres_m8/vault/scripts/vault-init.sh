#!/usr/bin/env sh
# Runs once as a one-shot Docker Compose service after Vault becomes healthy.
# Writes the per-service secrets into Vault KV v2 at secret/data/app.
# Idempotent: 'vault kv put' overwrites on each run, so this is safe to re-run.
set -e

echo "==> vault-init: connecting to ${VAULT_ADDR} ..."
until vault status >/dev/null 2>&1; do
    printf '.'
    sleep 1
done
echo " ready"

# Vault dev mode pre-mounts the 'secret/' KV v2 engine — no 'secrets enable' needed.
# Write the secrets that auth_user_service will pull via VaultProvider (REQUIRE_UPDATE_FIELDS).
vault kv put secret/app \
    "DB_PASSWORD=${AUTH_DB_PASSWORD}" \
    "REDIS_PASSWORD=${REDIS_PASSWORD}"

echo "==> vault-init: secrets written to secret/data/app"
echo "    Fields: DB_PASSWORD, REDIS_PASSWORD"
echo "==> vault-init: done — auth_user_service cleared to start"
