# vault_rs256_postgres_m8

**PostgreSQL 16** + **RS256 asymmetric token signing** + **HashiCorp Vault** secret
injection + stateful token mode + **Prometheus & Grafana** observability.

Access tokens are signed with a private RSA key (auth service only) and verified with
the corresponding public key (consumer services). Consumers discover the public key
automatically via the **JWKS endpoint** — no manual key distribution needed.

Sensitive secrets (`DB_PASSWORD`, `REDIS_PASSWORD`) are stored in HashiCorp Vault and
injected at startup via the built-in `VaultProvider` in `auth-sdk-m8`. The env files
for the auth service intentionally omit these fields.

**Choose this when:**

- You need PostgreSQL as the database engine.
- You want asymmetric RS256 signing with zero-downtime key rotation via JWKS.
- You want a secrets manager (Vault) integrated from day one, so credentials never
  live in plain `.env` files for the auth service.
- You are building toward a production-grade hardened setup.

> **Note on Vault image**: This stack uses `hashicorp/vault:1.17` — the hardened
> UBI9-based image. Update the tag to `hashicorp/vault:2.x-ubi` once Vault 2.x ships.
> The dev-mode configuration is identical across patch and minor versions.

---

## Architecture

```text
Browser → Traefik :9000 ──→ auth_user_service :8000   (RS256 issuer + Vault client)
                     └──→ fastapi_service :8000    (RS256 consumer via JWKS)
                          │
               ┌──────────┴──────────────────────────┐
               │           m8_app_network              │
               │                                       │
           m8_db (PostgreSQL 16)    redis_cache (Redis 7.4)
               │                                       │
           vault (HashiCorp Vault 1.17, dev mode)
               └── vault_init (one-shot secret loader)
               │
           prometheus + grafana (observability)
```

**Vault secret flow:**

```text
.env AUTH_DB_PASSWORD, REDIS_PASSWORD
        │
        ▼ (at compose up — via vault_init service)
vault kv put secret/app DB_PASSWORD=... REDIS_PASSWORD=...
        │
        ▼ (at auth_user_service startup — VaultProvider in auth-sdk-m8)
auth_user_service reads secret/data/app → injects into CommonSettings
```

---

## Services

| Service | Image | Accessible at |
| --- | --- | --- |
| traefik | traefik:v3.3 | `:8000` (HTTP), `:4430` (HTTPS), `:9000` (API), `:8080` (dashboard) |
| vault | hashicorp/vault:1.17 | `127.0.0.1:8200` (UI + API) |
| vault_init | hashicorp/vault:1.17 | one-shot init, no port |
| m8_db | postgres:16-alpine | `127.0.0.1:5432` |
| redis_cache | redis:7.4-alpine | `127.0.0.1:6379` |
| prometheus | ubuntu/prometheus:3.11-24.04_stable | `127.0.0.1:9090` |
| grafana | grafana/grafana:13.1.0 | `127.0.0.1:3000` |
| auth_user_service | local build | via Traefik at `/user` |
| fastapi_service | local build | via Traefik at `/fastapi` |

---

## Setup

### 1. Copy and edit the env files

```sh
cp .env.example .env
cp auth.env.example auth.env
cp api.env.example api.env
```

Open `.env` and replace every `changethis`:

```ini
DB_PASSWORD=<strong-postgres-root-password>
AUTH_DB_PASSWORD=<strong-auth-db-password>   # → stored in Vault as DB_PASSWORD
API_DB_PASSWORD=<strong-api-db-password>
REDIS_PASSWORD=<strong-redis-password>        # → stored in Vault as REDIS_PASSWORD
VAULT_DEV_TOKEN=<uuid>                        # python -c "import uuid; print(uuid.uuid4())"
```

Open `auth.env` and replace every `changethis`:

```ini
DB_USER=<same-as-AUTH_DB_USER-in-.env>
REFRESH_SECRET_KEY=<64-char-random>
PRIVATE_API_SECRET=<64-char-random>
TOKENS_ENCRYPTION_KEY=<64-char-random>
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=<strong-password>
```

`api.env` needs:

```ini
DB_USER=<same-as-API_DB_USER-in-.env>
DB_PASSWORD=<same-as-API_DB_PASSWORD-in-.env>
REDIS_PASSWORD=<same-as-REDIS_PASSWORD-in-.env>
REFRESH_SECRET_KEY=<64-char-random>
```

`ACCESS_KEY_ID` in `auth.env` can stay as `changethis_hex_kid` — `init.sh` derives and
writes the correct fingerprint automatically.

### 2. Generate RSA key pair + TLS certificates

```sh
bash init.sh
```

Generates `keys/private.pem`, `keys/public.pem`, derives a stable `kid`, writes
`ACCESS_KEY_ID` into `auth.env`, and creates the self-signed Traefik TLS certificate.

### 3. Start

```sh
docker compose up --build
```

**Startup order:**

1. `vault` starts (dev mode, in-memory KV).
2. `vault_init` waits for Vault to be healthy, then writes `DB_PASSWORD` and
   `REDIS_PASSWORD` to `secret/data/app`, then exits 0.
3. `m8_db` and `redis_cache` start in parallel.
4. `auth_user_service` starts after `vault_init` completes AND `m8_db`/`redis_cache`
   are healthy. VaultProvider reads `secret/data/app` and injects secrets into settings.
5. `fastapi_service` starts after `auth_user_service`.

Migrations run automatically on first boot. The superuser defined in `auth.env` is
created if it does not exist.

---

## How Vault secret injection works

`auth-sdk-m8` includes a `VaultProvider` that activates when:

- `ENVIRONMENT` is `staging` or `production`
- `SECRET_PROVIDER=vault`
- `VAULT_ADDR` and `VAULT_TOKEN` are set

It reads `secret/data/app` from the KV v2 engine and injects the following fields into
`CommonSettings` (overriding env-file values if present):

| Vault key | CommonSettings field | Notes |
| --- | --- | --- |
| `DB_PASSWORD` | `DB_PASSWORD` | Auth service DB password — omit from auth.env |
| `REDIS_PASSWORD` | `REDIS_PASSWORD` | Shared Redis password — omit from auth.env |

`VAULT_TOKEN` is passed from `.env` via the `environment` section in `docker-compose.yml`
and is intentionally absent from `auth.env`. For production, replace with a Docker secret
or Vault agent sidecar (see [Production hardening](#production-hardening)).

---

## How JWKS works in this stack

```text
Consumer receives JWT with header: {"alg": "RS256", "kid": "my-key-v1"}
         │
         ▼
Is "my-key-v1" in local cache?
   Yes → verify signature → done
   No  → GET http://auth_user_service:8000/user/.well-known/jwks.json
              │
              ▼  (returns all public keys indexed by kid)
         Cache result for JWKS_CACHE_TTL_SECONDS (default: 300 s)
         Verify signature → done
```

- **Key rotation**: run `bash init.sh --rotate-keys` → restart `auth_user_service` →
  consumers auto-refresh on the next unknown `kid`.
- **No manual key sync**: consumers only need `JWKS_URI` pointing to the auth service.

---

## Token mode: stateful

| Mode | Access token validated by | Refresh token | Redis round-trip per request |
| --- | --- | --- | --- |
| `stateless` | JWT signature only | JWT signature only | No |
| `hybrid` | JWT signature only | Redis allowlist | No |
| **`stateful`** | **JWT signature + Redis blacklist** | **Redis allowlist** | **Yes** |

In `stateful` mode, logout immediately invalidates the access token via the Redis
blacklist, regardless of its remaining lifetime.

---

## Vault dev mode notes

| Aspect | Dev mode (this stack) | Production recommendation |
| --- | --- | --- |
| Storage | In-memory — wiped on restart | File or Raft storage |
| Unseal | Auto-unsealed | Manual or auto-unseal (KMS) |
| Token | Root token (VAULT_DEV_TOKEN) | Scoped app token via policy |
| TLS | Disabled (internal Docker network) | Enable TLS on Vault listener |
| Persistence | Secrets lost on Vault restart | Persistent storage |

**If the vault container restarts** (e.g., `docker compose restart vault`), dev-mode
secrets are wiped. Re-populate them with:

```sh
docker compose start vault_init
```

This re-runs `vault-init.sh` which is idempotent — safe to run at any time.

---

## Database isolation

This stack defaults to **Scenario 2** (per-service isolation): `auth_db` and `api_db`
are created as separate databases with separate users on first volume init.

Database provisioning runs **once** on first volume creation. To reprovision:
`bash init.sh --reset-db`.

---

## Observability

### Grafana — `http://localhost:3000`

Pre-provisioned with a Prometheus datasource. Default credentials: `admin` / `foobar`.

### Prometheus — `http://localhost:9090`

Scrapes `/user/metrics` and `/fastapi/metrics` from both services.

### Vault UI — `http://localhost:8200`

Vault dev-mode UI. Log in with `VAULT_DEV_TOKEN` from `.env`. Use it to inspect
`secret/data/app` or test token policies.

---

## URLs

| What | URL |
| --- | --- |
| Auth API | `http://localhost:9000/user/` |
| Auth interactive docs | `http://localhost:9000/user/docs` |
| JWKS endpoint | `http://localhost:9000/user/.well-known/jwks.json` |
| FastAPI service docs | `http://localhost:9000/fastapi/docs` |
| Vault UI | `http://localhost:8200` |
| Traefik dashboard | `http://localhost:8080` |
| Prometheus | `http://localhost:9090` |
| Grafana | `http://localhost:3000` |
| HTTPS | `https://localhost:4430/user/docs` (self-signed cert — accept browser warning) |

---

## Port map

| Port | Bound to | Purpose |
| --- | --- | --- |
| `8000` | `0.0.0.0` | Traefik HTTP |
| `4430` | `0.0.0.0` | Traefik HTTPS |
| `9000` | `127.0.0.1` | API services entry (set `API_BIND_IP` in `.env` to expose on LAN) |
| `8080` | `127.0.0.1` | Traefik dashboard |
| `8200` | `127.0.0.1` | HashiCorp Vault |
| `5432` | `127.0.0.1` | PostgreSQL |
| `6379` | `127.0.0.1` | Redis |
| `9090` | `127.0.0.1` | Prometheus |
| `3000` | `127.0.0.1` | Grafana |

---

## Configuration reference

### `.env` — infrastructure + Vault bootstrap

| Variable | Notes |
| --- | --- |
| `DB_USER` | PostgreSQL superuser for engine bootstrap (not used by app services) |
| `DB_PASSWORD` | PostgreSQL superuser password |
| `DB_PORT` | PostgreSQL port (default `5432`) |
| `AUTH_DB_USER/PASSWORD/NAME` | Per-service auth DB credentials — also written to Vault |
| `API_DB_USER/PASSWORD/NAME` | Per-service API DB credentials — NOT written to Vault |
| `REDIS_PASSWORD` | Redis password — also written to Vault |
| `VAULT_DEV_TOKEN` | Dev-mode root token. Use a UUID. |

### `auth.env` — auth service (issuer)

| Variable | Source | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | auth.env | Must be `staging` or `production` to activate Vault |
| `SECRET_PROVIDER` | auth.env | Set to `vault` |
| `VAULT_ADDR` | auth.env | `http://vault:8200` — internal Docker service name |
| `VAULT_TOKEN` | compose `environment` | Injected from `VAULT_DEV_TOKEN` in `.env` |
| `DB_PASSWORD` | **Vault** | Omit from auth.env — Vault provides it |
| `REDIS_PASSWORD` | **Vault** | Omit from auth.env — Vault provides it |
| `DB_USER` | auth.env | Must match `AUTH_DB_USER` in `.env` |
| `ACCESS_PRIVATE_KEY_FILE` | auth.env | `/opt/keys/private.pem` |
| `ACCESS_PUBLIC_KEY_FILE` | auth.env | `/opt/keys/public.pem` |
| `REFRESH_SECRET_KEY` | auth.env | HMAC secret for refresh tokens |
| `PRIVATE_API_SECRET` | auth.env | Secret for `X-Internal-Token` headers |
| `TOKENS_ENCRYPTION_KEY` | auth.env | Fernet key for encrypting refresh token payloads |

### `api.env` — consumer service

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` — verifies tokens via JWKS |
| `JWKS_URI` | `http://auth_user_service:8000/user/.well-known/jwks.json` |
| `DB_USER/DB_PASSWORD` | API service DB credentials — from api.env directly (no Vault) |

---

## Production hardening

### 1. Switch Vault to server mode

Replace the `vault` service in `docker-compose.yml`:

```yaml
vault:
  image: hashicorp/vault:1.17
  cap_add:
    - IPC_LOCK
  command: ["vault", "server", "-config=/vault/config/vault.hcl"]
  volumes:
    - ./vault/config/vault.hcl:/vault/config/vault.hcl:ro
    - ./vault/data:/vault/data
```

Use `vault/config/vault.hcl`:

```hcl
storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1   # enable TLS for production
}

ui = true
```

Initialize: `vault operator init`, save unseal keys and root token securely.

### 2. Create a scoped app token

Apply `vault/policies/app-policy.hcl` and issue a limited token:

```sh
vault policy write app-read vault/policies/app-policy.hcl
APP_TOKEN=$(vault token create -policy=app-read -period=24h -format=json | jq -r .auth.client_token)
```

Pass `APP_TOKEN` as a Docker secret instead of the root token:

```yaml
secrets:
  vault_token:
    file: ./secrets/vault_token   # write APP_TOKEN here

auth_user_service:
  secrets:
    - vault_token
  # Remove VAULT_TOKEN from environment — VaultProvider reads /run/secrets/vault_token
```

### 3. Use Vault agent for automatic token renewal

Add a Vault agent sidecar that handles token renewal and writes secrets to shared
volume, then mount the output into the app container. See the
[Vault Agent documentation](https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent).

---

## Key rotation procedure

```sh
# 1. Regenerate the RSA key pair and update ACCESS_KEY_ID in auth.env
bash init.sh --rotate-keys

# 2. Restart the auth service (picks up new private key + kid)
docker compose up -d --build auth_user_service

# 3. Consumers self-update automatically — no restart needed
```

Old tokens remain valid until they expire. After `JWKS_CACHE_TTL_SECONDS` the cache
refreshes; tokens with the old `kid` will then fail verification.

---

## Common operations

```sh
# Start in background
docker compose up -d --build

# Re-populate Vault after a vault container restart (dev mode wipes in-memory state)
docker compose start vault_init

# Follow auth service logs
docker compose logs -f auth_user_service

# Inspect Vault secrets
VAULT_ADDR=http://localhost:8200 VAULT_TOKEN=<your-VAULT_DEV_TOKEN> vault kv get secret/app

# Verify JWKS endpoint
curl http://localhost:9000/user/.well-known/jwks.json | python -m json.tool

# Full reset — stops containers and wipes the database
bash init.sh --reset-db
```

---

## Troubleshooting

**auth_user_service fails to start — VaultProvider error**
Vault may not be ready or vault_init may have failed. Check:

```sh
docker compose logs vault_init
docker compose logs vault
```

If vault restarted after vault_init completed, re-run: `docker compose start vault_init`,
then restart auth: `docker compose restart auth_user_service`.

**`VAULT_TOKEN` is empty or wrong**
Ensure `VAULT_DEV_TOKEN` is set in `.env` and that you ran `docker compose up` (not just
`docker compose restart`) after editing `.env`.

**Auth service fails — key file not found**
Run `bash init.sh` to generate `keys/private.pem` and `keys/public.pem`.

**JWKS endpoint returns empty `keys` array**
The auth service started before the key files were mounted. Restart:
`docker compose restart auth_user_service`.

**`changethis` rejection on startup**
Replace all `changethis` values. For RS256, `ACCESS_SECRET_KEY` must be absent (not set).

**Port conflict**
Identify with `netstat -ano | findstr <PORT>` (Windows) or `lsof -i :<PORT>` (Mac/Linux).
