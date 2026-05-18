# vault/config/vault.hcl — Minimal Vault server config.
# Used by vault/docker-compose.vault.yml (server mode, persistent file storage).
#
# For production:
#   - Prefer Raft integrated storage over "file" (built-in HA, no external deps).
#   - Enable TLS: uncomment tls_cert_file / tls_key_file and set tls_disable = false.
#   - Set api_addr to the hostname that other services use to reach Vault.

storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
  # For TLS (recommended in production):
  # tls_disable      = false
  # tls_cert_file    = "/vault/certs/vault.crt"
  # tls_key_file     = "/vault/certs/vault.key"
}

ui = true
