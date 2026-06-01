# vault_m8

**PostgreSQL 16** + **RS256 asymmetric token signing** + **HashiCorp Vault** secret injection + **stateful** token mode + **Prometheus & Grafana** observability.

The auth service's database password and Redis password are stored in HashiCorp Vault and injected at startup via the `VaultProvider` in `auth-sdk-m8`. `auth.env` intentionally omits these two fields — the auth service never reads them from a file.

> **What Vault protects here (and what it does not):** `DB_PASSWORD` and `REDIS_PASSWORD` are absent from `auth.env`. However, they are still present in the shared `.env` file because the PostgreSQL container and the `vault_init` bootstrap service need them. In this stack, `.env` is the bootstrap source of truth. In a real production deployment you would replace that `.env` with CI/CD variable injection or Docker secrets — see [Recommended production architecture](#recommended-production-architecture).

**Choose this when:**

- You need PostgreSQL as the database engine.
- You want asymmetric RS256 signing with zero-downtime key rotation via JWKS.
- You want to learn or test the `VaultProvider` injection pattern before wiring it into a real Vault deployment.

---

## Summary

- [This stack is an example — not production-ready as-is](#this-stack-is-an-example--not-production-ready-as-is)
  - [What the stack still exposes in plaintext](#what-the-stack-still-exposes-in-plaintext)
  - [Vault in the same compose vs. separate deployment](#vault-in-the-same-compose-vs-separate-deployment)
- [Architecture](#architecture)
- [Services](#services)
- [Setup](#setup)
- [How Vault secret injection works](#how-vault-secret-injection-works)
- [How JWKS works](#how-jwks-works)
- [Token mode: stateful](#token-mode-stateful)
- [Vault dev mode notes](#vault-dev-mode-notes)
- [Recommended production architecture](#recommended-production-architecture)
- [Using with an external Vault](#using-with-an-external-vault)
- [Observability](#observability)
- [URLs](#urls)
- [Port map](#port-map)
- [Configuration reference](#configuration-reference)
- [Key rotation](#key-rotation)
- [Common operations](#common-operations)
- [Live testing](#live-testing)
- [Troubleshooting](#troubleshooting)

---

## This stack is an example — not production-ready as-is

> **Important:** The Vault configuration in this stack uses **dev mode** — an ephemeral, in-memory Vault that auto-unseals on startup and loses all data on restart. It is intentionally simple for learning and local testing.
>
> **Do not use this compose file in production without the changes listed in [Recommended production architecture](#recommended-production-architecture).**

### What the stack still exposes in plaintext

Even with Vault, the shared `.env` file still contains plaintext secrets:

| Secret in `.env` | Why it is there | How to eliminate it in production |
| --- | --- | --- |
| `DB_PASSWORD` (Postgres superuser) | Required by the `postgres:16-alpine` container on first boot | Pre-provision the DB outside compose; inject via CI/CD variable |
| `AUTH_DB_PASSWORD` | Used by `vault_init` to write the secret to Vault | Inject via CI/CD or a secrets bootstrap pipeline |
| `REDIS_PASSWORD` | Used by `vault_init` to write the secret to Vault | Same as above |
| `VAULT_DEV_TOKEN` | Required to authenticate to Vault dev mode | Replace with Docker secret or AppRole — never in `.env` |

The `auth_user_service` container does **not** read `DB_PASSWORD` or `REDIS_PASSWORD` from env files — it gets them from Vault. But the bootstrap infrastructure still needs a source of truth. Removing that from `.env` is part of a full production hardening.

### Vault in the same compose vs. separate deployment

This stack bundles Vault inside the same `docker-compose.yml` as the application services. That is convenient for learning but wrong for production:

| Aspect | Bundled (this stack) | Separate (production) |
| --- | --- | --- |
| Lifecycle | Vault starts and stops with the app | Vault is long-lived infrastructure, independent of the app |
| Data | Wiped on `docker compose down` (dev mode) | Persistent storage, outlives any single deployment |
| Access | All compose services share a network with Vault | Vault exposed only to specific services via firewall/network policy |
| Token scope | Root token in `.env` | Scoped app token, auto-renewed by Vault Agent |
| Init | `vault_init` runs `kv put` at compose start | Secrets pre-loaded by your secrets-management pipeline |

**Recommendation:** treat Vault as a separate infrastructure component — either a managed service (HCP Vault, AWS Secrets Manager), a dedicated Docker Compose stack (`vault.docker-compose.yml`), or a Kubernetes deployment. The app compose should only contain `VAULT_ADDR` and the authentication method — not the Vault server itself.

| What this stack demonstrates | What you must change for production |
| --- | --- |
| `VaultProvider` injection pattern | Pre-existing Vault with persistent storage (not dev mode) |
| Secrets absent from `auth.env` | Also remove `DB_PASSWORD` / `REDIS_PASSWORD` / `VAULT_DEV_TOKEN` from `.env` |
| `vault_init` bootstrap service | Replace with your secrets-management pipeline |
| Root token usage | Scope to a policy; use AppRole or Kubernetes auth |
| Vault bundled in app compose | Move Vault to its own stack / managed service |
| TLS disabled on Vault listener | Enable TLS on the Vault listener |

The compose file is structured to make the Vault integration pattern clear and testable. Treat it as a reference implementation, not a deployment template.

---

## Architecture

```text
Browser / Frontend
       │
       ▼
  Traefik :9000
       │
       ├──► /user/*      → auth_user_service :8000  (RS256 issuer + Vault client)
       └──► /fastapi/*   → fastapi_service :8000    (RS256 consumer via JWKS)
                │
       ┌────────┴──────────────────────────┐
       ▼                                   ▼
  m8_db (PostgreSQL 16)          redis_cache (Redis 7.4)
       │                                   │
  vault (HashiCorp Vault 1.17, dev mode)
       └── vault_init (one-shot secret loader)
       │
  Prometheus :9090 + Grafana :3000
```

**Vault secret flow:**

```text
.env  AUTH_DB_PASSWORD, REDIS_PASSWORD
        │
        ▼  (at compose up — via vault_init service)
vault kv put secret/app DB_PASSWORD=... REDIS_PASSWORD=...
        │
        ▼  (at auth_user_service startup — VaultProvider in auth-sdk-m8)
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
| auth_user_service | [tepochtli/fa-auth-m8:latest](https://hub.docker.com/r/tepochtli/fa-auth-m8) | via Traefik at `/user` |
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

Open `api.env` and replace:

```ini
DB_USER=<same-as-API_DB_USER-in-.env>
DB_PASSWORD=<same-as-API_DB_PASSWORD-in-.env>
REDIS_PASSWORD=<same-as-REDIS_PASSWORD-in-.env>
REFRESH_SECRET_KEY=<64-char-random>
```

`ACCESS_KEY_ID` in `auth.env` can stay as `changethis_hex_kid` — `init.sh` derives and writes the correct fingerprint automatically.

### 2. Generate RSA key pair + TLS certificates

```sh
bash init.sh
```

### 3. Start

```sh
docker compose up -d
```

`auth_user_service` uses a pre-built image from Docker Hub — no `--build` needed. Only `fastapi_service` is built locally.

**Startup order:**

1. `vault` starts (dev mode, in-memory KV).
2. `vault_init` waits for Vault to be healthy, then writes `DB_PASSWORD` and `REDIS_PASSWORD` to `secret/data/app`, then exits 0.
3. `m8_db` and `redis_cache` start in parallel.
4. `auth_user_service` starts after `vault_init` completes AND `m8_db`/`redis_cache` are healthy. `VaultProvider` reads `secret/data/app` and injects secrets into settings.
5. `fastapi_service` starts after `auth_user_service`.

---

## How Vault secret injection works

`auth-sdk-m8` includes a `VaultProvider` that activates when:

- `ENVIRONMENT` is `staging` or `production`
- `SECRET_PROVIDER=vault`
- `VAULT_ADDR` and `VAULT_TOKEN` are set

It reads `secret/data/app` from the KV v2 engine and injects:

| Vault key | CommonSettings field | Notes |
| --- | --- | --- |
| `DB_PASSWORD` | `DB_PASSWORD` | Auth service DB password — omit from `auth.env` |
| `REDIS_PASSWORD` | `REDIS_PASSWORD` | Shared Redis password — omit from `auth.env` |

`VAULT_TOKEN` is passed from `.env` via the `environment` section in `docker-compose.yml` and is intentionally absent from `auth.env`.

---

## How JWKS works

```text
Consumer receives JWT with header: {"alg": "RS256", "kid": "abc123"}
         │
         ▼
Is "abc123" in local cache?
   Yes → verify signature → done
   No  → GET http://auth_user_service:8000/user/.well-known/jwks.json
              │
              ▼
         Cache result for JWKS_CACHE_TTL_SECONDS (default: 300 s)
         Verify signature → done
```

---

## Token mode: stateful

| Mode | Access token validated by | Refresh token | Redis round-trip per request |
| --- | --- | --- | --- |
| `stateless` | JWT signature only | JWT signature only | No |
| `hybrid` | JWT signature only | Redis allowlist | No |
| **`stateful`** | **JWT signature + Redis blacklist** | **Redis allowlist** | **Yes** |

In `stateful` mode, logout immediately invalidates the access token via the Redis blacklist, regardless of its remaining lifetime.

---

## Vault dev mode notes

| Aspect | Dev mode (this stack) | Why it matters |
| --- | --- | --- |
| Storage | **In-memory — wiped on restart** | All secrets lost if vault container restarts |
| Unseal | Auto-unsealed at startup | No unseal keys to manage (convenient but insecure) |
| Token | Root token (`VAULT_DEV_TOKEN`) | Full Vault access — no least-privilege |
| TLS | Disabled | Traffic between containers is unencrypted |
| Persistence | None | Not suitable for persistent workloads |

**If the vault container restarts**, dev-mode secrets are wiped. Re-populate them with:

```sh
docker compose start vault_init
```

This re-runs `vault-init.sh` which is idempotent — safe to run at any time.

---

## Recommended production architecture

The following changes are required before using Vault in a real deployment:

### 1. Switch to Vault server mode

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

`vault/config/vault.hcl` (minimal):

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

Initialize with `vault operator init`, save unseal keys and root token securely, then unseal.

### 2. Use a scoped app token (not the root token)

```sh
vault policy write app-read vault/policies/app-policy.hcl
APP_TOKEN=$(vault token create -policy=app-read -period=24h -format=json | jq -r .auth.client_token)
```

Pass `APP_TOKEN` as a Docker secret:

```yaml
secrets:
  vault_token:
    file: ./secrets/vault_token

auth_user_service:
  secrets:
    - vault_token
  # Remove VAULT_TOKEN from environment: section
  # VaultProvider reads /run/secrets/vault_token automatically
```

### 3. Use Vault Agent for automatic token renewal

Add a Vault Agent sidecar that handles token renewal and writes secrets to a shared volume mounted into the app container. See the [Vault Agent documentation](https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent).

### 4. Enable TLS on the Vault listener

Set `tls_cert_file` and `tls_key_file` in `vault.hcl` and set `VAULT_SKIP_VERIFY=false` in all clients.

### 5. Use AppRole or Kubernetes auth instead of static tokens

Static tokens work for single-machine setups. For multi-node or Kubernetes deployments, use [AppRole](https://developer.hashicorp.com/vault/docs/auth/approle) or the Kubernetes auth method so each service authenticates with short-lived credentials.

---

## Using with an external Vault

The bundled `vault` service is for learning and local testing only. For any persistent
deployment, run Vault as a separate stack or use a managed service.

### Which approach to choose

| Scenario | Recommended approach |
| --- | --- |
| Local development / CI | Bundled dev-mode Vault (this compose file) |
| Local integration testing with persistence | Separate local Vault — `vault/docker-compose.vault.yml` |
| Staging / production | Managed Vault (HCP Vault, AWS Secrets Manager) or a dedicated Vault cluster |

### Option A — Separate local Vault compose

`vault/docker-compose.vault.yml` runs Vault in server mode with persistent file
storage. Unlike the bundled dev mode, secrets survive container restarts.

```sh
# Start Vault (first time — follow the init steps printed in the file header)
docker compose -f vault/docker-compose.vault.yml up -d

# Initialize and unseal (see vault/docker-compose.vault.yml for full instructions)
docker compose -f vault/docker-compose.vault.yml exec vault_server vault operator init
# Unseal with 3 of the 5 keys, then write secrets and create a scoped token.
```

After init, write a scoped app token to a secrets file:

```sh
mkdir -p secrets
echo "<scoped-app-token>" > secrets/vault_token
chmod 600 secrets/vault_token
```

Then update `docker-compose.yml` to remove the bundled Vault and point
`auth_user_service` at the external Vault:

```yaml
services:
  auth_user_service:
    environment:
      SECRET_PROVIDER: vault
      VAULT_ADDR: http://host.docker.internal:8200   # host from inside container
    secrets:
      - vault_token
    # Remove VAULT_TOKEN from environment — VaultProvider reads /run/secrets/vault_token

secrets:
  vault_token:
    file: ./secrets/vault_token
```

Remove the `vault` and `vault_init` service blocks from `docker-compose.yml` and
drop the `vault_init` condition from `auth_user_service.depends_on`.

### Option B — Managed Vault (HCP Vault, cloud secrets manager)

Point `VAULT_ADDR` at your managed service endpoint. The `VaultProvider` in
`auth-sdk-m8` only needs `VAULT_ADDR`, `VAULT_TOKEN` (or AppRole credentials), and
the secret path — it does not care whether Vault is local or remote.

```yaml
services:
  auth_user_service:
    environment:
      SECRET_PROVIDER: vault
      VAULT_ADDR: https://vault.example.com:8200
    secrets:
      - vault_token

secrets:
  vault_token:
    file: ./secrets/vault_token   # or use a CI/CD injected Docker secret
```

### Production env examples

Two example files show what configuration looks like without the bundled Vault:

| File | Purpose |
| --- | --- |
| [`.env.prod_example`](.env.prod_example) | `.env` with `AUTH_DB_PASSWORD`, `REDIS_PASSWORD`, and `VAULT_DEV_TOKEN` removed — shows what CI/CD injects |
| [`auth.env.prod_example`](auth.env.prod_example) | `auth.env` with `ENVIRONMENT=production`, `SET_DOCS=false`, and no DB/Redis passwords |

Copy and adapt these instead of `*.example` when targeting a staging or production
environment.

### Extending Vault coverage

`DB_PASSWORD` and `REDIS_PASSWORD` are the only secrets currently stored in Vault.
You can extend coverage by adding more fields to `vault-init.sh` and to the
`app-policy.hcl` read policy:

```sh
# In your secrets pipeline (or vault-init.sh equivalent):
vault kv put secret/app \
  DB_PASSWORD=<auth-db-password> \
  REDIS_PASSWORD=<redis-password> \
  REFRESH_SECRET_KEY=<value> \
  PRIVATE_API_SECRET=<value> \
  TOKENS_ENCRYPTION_KEY=<value>
```

Then remove the corresponding fields from `auth.env` — `VaultProvider` will inject
them at startup. Update `app-policy.hcl` if you add paths.

---

## Observability

### Grafana — `http://localhost:3000`

Pre-provisioned with a Prometheus datasource. Default credentials: `admin` / `foobar`.

### Prometheus — `http://localhost:9090`

Scrapes `/user/metrics` and `/fastapi/metrics` from both services.

### Vault UI — `http://localhost:8200`

Dev-mode Vault UI. Log in with `VAULT_DEV_TOKEN` from `.env`. Use it to inspect `secret/data/app` or test token policies.

---

## URLs

| What | URL |
| --- | --- |
| Auth API | `http://localhost:9000/user/` |
| Auth interactive docs | `http://localhost:9000/user/docs` |
| JWKS endpoint | `http://localhost:9000/user/.well-known/jwks.json` |
| FastAPI service docs | `http://localhost:9000/fastapi/docs` |
| Health check | `http://localhost:9000/user/health/` |
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
| `DB_USER` | PostgreSQL superuser for engine bootstrap |
| `DB_PASSWORD` | PostgreSQL superuser password |
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
| `LOGIN_RATE_LIMIT_REQUESTS` | auth.env | Max login attempts per window per email (default: 5) |
| `LOGIN_RATE_LIMIT_WINDOW_MINUTES` | auth.env | Login rate-limit window in minutes (default: 15) |
| `REFRESH_RATE_LIMIT_REQUESTS` | auth.env | Max refresh rotations per window per user (default: 10) |
| `REFRESH_RATE_LIMIT_WINDOW_MINUTES` | auth.env | Refresh rate-limit window in minutes (default: 5) |
| `TRUSTED_PROXY_COUNT` | auth.env | Trusted proxy hops for real client IP extraction (default: 1). Set to `0` if no proxy in front. |

### `api.env` — consumer service

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` — verifies tokens via JWKS |
| `JWKS_URI` | `http://auth_user_service:8000/user/.well-known/jwks.json` |
| `DB_USER/DB_PASSWORD` | API service DB credentials — from api.env directly (no Vault) |

---

## Key rotation

```sh
# 1. Regenerate the RSA key pair and update ACCESS_KEY_ID in auth.env
bash init.sh --rotate-keys

# 2. Restart the auth service (picks up new private key + kid)
docker compose up -d --build auth_user_service

# 3. Consumers self-update automatically — no restart needed
```

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

# Full reset
bash init.sh --reset-db
```

---

## Live testing

Run the live test suite against this stack (requires the stack to be up):

```sh
# From the repo root
pytest -m live_asymmetric --no-cov   # RS256/ES256-specific attacks
pytest -m live_stateful --no-cov     # Token revocation guarantees
pytest -m live_security --no-cov     # Universal attack categories (A–M)
```

Manual smoke test:

```sh
curl http://localhost:9000/user/health/
# Expected: {"status":"ok","token_mode":"stateful","redis":"ok","database":"ok",...}
```

---

## Production deployment

When deploying publicly, replace `traefik/dynamic_conf.yml` with `traefik/production_dynamic_conf.yml`. The production config:

- Adds `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` to all API routes.
- Enables `Strict-Transport-Security` (HSTS). Only use after TLS is stable with a trusted certificate.
- Dev `dynamic_conf.yml` has no CSP so Swagger UI works during development.

Also update the `Host` rules in the production config to match your actual FQDN.

---

## Troubleshooting

**auth_user_service fails to start — VaultProvider error** — Vault may not be ready or vault_init may have failed:

```sh
docker compose logs vault_init
docker compose logs vault
```

If vault restarted after vault_init completed, re-run: `docker compose start vault_init`, then restart auth: `docker compose restart auth_user_service`.

**`VAULT_TOKEN` is empty or wrong** — ensure `VAULT_DEV_TOKEN` is set in `.env` and that you ran `docker compose up` (not just `docker compose restart`) after editing `.env`.

**Auth service fails — key file not found** — run `bash init.sh` to generate `keys/private.pem` and `keys/public.pem`.

**JWKS endpoint returns empty `keys` array** — restart: `docker compose restart auth_user_service`.

**`changethis` rejection on startup** — replace all `changethis` values. For RS256, `ACCESS_SECRET_KEY` must be absent (not set).

---

> [Docker Compose examples](../README.md) · [Repository root](https://github.com/mano8/fa-auth-m8/tree/main)
