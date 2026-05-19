# lite_es256_m8

**MariaDB 12** + **ES256 asymmetric token signing** (ECDSA P-256) + **stateful** token mode. No monitoring services.

Access tokens are signed with a private EC key (auth service only) and verified with the corresponding public key (consumer services). Consumers discover the public key automatically via the **JWKS endpoint** — no manual key distribution required.

**Choose this when:** you need ECDSA-based asymmetric signing. ES256 produces shorter signatures than RS256 and is preferred for constrained environments.

---

## Summary

- [Architecture](#architecture)
- [Services](#services)
- [Limitations](#limitations)
- [ES256 vs RS256](#es256-vs-rs256)
- [Setup](#setup)
- [How JWKS works](#how-jwks-works)
- [Token mode: stateful](#token-mode-stateful)
- [URLs](#urls)
- [Port map](#port-map)
- [Configuration reference](#configuration-reference)
- [Key rotation](#key-rotation)
- [Volumes](#volumes)
- [Database isolation](#database-isolation)
- [Common operations](#common-operations)
- [Live testing](#live-testing)
- [Troubleshooting](#troubleshooting)

---

## Architecture

```text
Browser / Frontend
       │
       ▼
  Traefik :9000
       │
       ├──► /user/*      → auth_user_service :8000  (ES256 issuer)
       └──► /fastapi/*   → fastapi_service :8000    (ES256 consumer via JWKS)
                │
       ┌────────┴────────┐
       ▼                 ▼
  m8_db (MariaDB 12)  redis_cache (Redis 7.4)
```

The auth service holds the **private EC key** and issues signed tokens. The fastapi service holds **no key** — it verifies tokens by fetching the public key from the JWKS endpoint.

---

## Services

| Service | Image | Accessible at |
| --- | --- | --- |
| traefik | traefik:v3.3 | `:8000` (HTTP), `:4430` (HTTPS), `:9000` (API), `:8080` (dashboard) |
| m8_db | mariadb:12-ubi | `127.0.0.1:3306` |
| redis_cache | redis:7.4-alpine | `127.0.0.1:6379` |
| auth_user_service | local build | via Traefik at `/user` |
| fastapi_service | local build | via Traefik at `/fastapi` |

---

## Limitations

- **No Prometheus / Grafana.** Use [stateful_m8](../stateful_m8/) or [env_rs256_m8](../env_rs256_m8/) if you need dashboards.
- **No Vault.** The EC private key is stored as a file mounted into the container. Use [vault_rs256_postgres_m8](../vault_rs256_postgres_m8/) for secrets-manager integration (RS256 variant).
- **MariaDB only.** No PostgreSQL variant of this stack is provided.
- **`auth.env.example` is pre-configured for ES256** — `ACCESS_TOKEN_ALGORITHM=ES256` is already set. Run `bash init.sh` to generate the EC key pair.

---

## ES256 vs RS256

Both are asymmetric algorithms using the same JWKS distribution mechanism. The difference is the key type:

| Aspect | RS256 (RSA) | ES256 (ECDSA P-256) |
| --- | --- | --- |
| Key size | 2048-bit RSA key | 256-bit EC key |
| Signature size | ~342 bytes (base64) | ~86 bytes (base64) |
| Key generation | `openssl genrsa -out private.pem 2048` | `openssl ecparam -genkey -name prime256v1 ...` |
| `init.sh` support | ✅ automatic | ✅ automatic (detects algorithm from `auth.env`) |
| JWKS `kty` | `RSA` | `EC` with `crv: P-256` |

ES256 tokens are more compact, which matters for HTTP headers and mobile clients. Both offer equivalent security for typical web applications.

---

## Setup

### 1. Copy and edit the env files

```sh
cp auth.env.example auth.env
cp api.env.example api.env
```

Open `auth.env` and set the following (replace every `changethis`):

```ini
# Algorithm — must be ES256 for this stack
ACCESS_TOKEN_ALGORITHM=ES256
REFRESH_TOKEN_ALGORITHM=HS256

FIRST_SUPERUSER="admin@example.com"
FIRST_SUPERUSER_PASSWORD="a-strong-password"

REFRESH_SECRET_KEY="<generate>"
DB_PASSWORD="<generate>"
DB_ROOT_PASSWORD="<generate>"
REDIS_PASSWORD="<generate>"
PRIVATE_API_SECRET="<generate>"
TOKENS_ENCRYPTION_KEY="<generate>"
```

Leave `ACCESS_KEY_ID=changethis_hex_kid` as-is — `init.sh` derives it automatically.

> **Note:** `auth.env.example` already has `ACCESS_TOKEN_ALGORITHM=ES256`. Run `init.sh` after copying to generate the EC key pair.

Open `api.env` and set:

```ini
ACCESS_TOKEN_ALGORITHM=ES256
JWKS_URI=http://auth_user_service:8000/user/.well-known/jwks.json
```

### 2. Generate EC key pair + TLS certificates

```sh
bash init.sh
```

> **Windows:** use **Git Bash** or **WSL**.

`init.sh` reads `ACCESS_TOKEN_ALGORITHM` from `auth.env` and generates the correct key type. For ES256 it runs:

```sh
openssl ecparam -genkey -name prime256v1 -noout -out keys/private.pem
openssl ec -in keys/private.pem -pubout -out keys/public.pem
```

It also derives a stable `kid` from the key fingerprint and writes `ACCESS_KEY_ID` into `auth.env`.

### 3. Start

```sh
docker compose up --build
```

Migrations run automatically on first boot. The superuser defined in `auth.env` is created if it does not exist.

---

## How JWKS works

```text
Consumer receives JWT with header: {"alg": "ES256", "kid": "abc123"}
         │
         ▼
Is "abc123" in local cache?
   Yes → verify signature → done
   No  → GET http://auth_user_service:8000/user/.well-known/jwks.json
              │
              ▼  (returns EC public keys indexed by kid)
         Cache result for JWKS_CACHE_TTL_SECONDS (default: 300 s)
         Verify signature → done
```

The JWKS response for ES256 uses `"kty": "EC"` with `"crv": "P-256"`:

```json
{
  "keys": [{
    "kty": "EC",
    "use": "sig",
    "alg": "ES256",
    "kid": "abc123",
    "crv": "P-256",
    "x": "...",
    "y": "..."
  }]
}
```

The JWKS endpoint (no auth required):

```text
http://localhost:9000/user/.well-known/jwks.json
```

---

## Token mode: stateful

This stack defaults to `TOKEN_MODE=stateful`:

| Mode | Access token validated by | Refresh token | Redis round-trip per request |
| --- | --- | --- | --- |
| `stateless` | JWT signature only | JWT signature only | No |
| `hybrid` | JWT signature only | Redis allowlist | No |
| **`stateful`** | **JWT signature + Redis blacklist** | **Redis allowlist** | **Yes** |

In `stateful` mode, logout immediately invalidates the access token via the Redis blacklist, regardless of its remaining lifetime.

---

## URLs

| What | URL |
| --- | --- |
| Auth API | `http://localhost:9000/user/` |
| Auth interactive docs | `http://localhost:9000/user/docs` |
| JWKS endpoint | `http://localhost:9000/user/.well-known/jwks.json` |
| FastAPI service docs | `http://localhost:9000/fastapi/docs` |
| Health check | `http://localhost:9000/user/health/` |
| Traefik dashboard | `http://localhost:8080` |
| HTTPS | `https://localhost:4430/user/docs` (self-signed cert — accept browser warning) |

---

## Port map

| Port | Bound to | Purpose |
| --- | --- | --- |
| `8000` | `0.0.0.0` | Traefik HTTP |
| `4430` | `0.0.0.0` | Traefik HTTPS |
| `9000` | `127.0.0.1` | API services entry (set `API_BIND_IP` in `auth.env` to expose on LAN) |
| `8080` | `127.0.0.1` | Traefik dashboard |
| `3306` | `127.0.0.1` | MariaDB |
| `6379` | `127.0.0.1` | Redis |

---

## Configuration reference

### `auth.env` — auth service (issuer)

| Variable | Value | Notes |
| --- | --- | --- |
| `ACCESS_TOKEN_ALGORITHM` | `ES256` | Must be set — example file defaults to RS256 |
| `REFRESH_TOKEN_ALGORITHM` | `HS256` | Refresh tokens remain symmetric |
| `ACCESS_PRIVATE_KEY_FILE` | `/opt/keys/private.pem` | EC private key path inside the container |
| `ACCESS_PUBLIC_KEY_FILE` | `/opt/keys/public.pem` | EC public key path inside the container |
| `ACCESS_KEY_ID` | — | Stable `kid` written by `init.sh` |
| `REFRESH_SECRET_KEY` | — | HMAC secret for refresh tokens |
| `TOKEN_MODE` | `stateful` | `stateless` / `hybrid` / `stateful` |
| `AUTH_SERVICE_ROLE` | `issuer` | Signs tokens with the EC private key |
| `LOGIN_RATE_LIMIT_REQUESTS` | `5` | Max login attempts per window per email |
| `LOGIN_RATE_LIMIT_WINDOW_MINUTES` | `15` | Login rate-limit window in minutes |
| `REFRESH_RATE_LIMIT_REQUESTS` | `10` | Max refresh rotations per window per user |
| `REFRESH_RATE_LIMIT_WINDOW_MINUTES` | `5` | Refresh rate-limit window in minutes |

### `api.env` — consumer service

| Variable | Value | Notes |
| --- | --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` | Verifies tokens via JWKS, does not sign them |
| `ACCESS_TOKEN_ALGORITHM` | `ES256` | Must match auth service |
| `JWKS_URI` | `http://auth_user_service:8000/user/.well-known/jwks.json` | JWKS endpoint |
| `JWKS_CACHE_TTL_SECONDS` | `300` | How long to cache the public key |

---

## Key rotation

```sh
# 1. Regenerate the EC key pair and update ACCESS_KEY_ID in auth.env
bash init.sh --rotate-keys

# 2. Restart the auth service (picks up new private key + kid)
docker compose up -d --build auth_user_service

# 3. Consumers self-update — no restart needed
```

Old tokens remain valid until they expire. After `JWKS_CACHE_TTL_SECONDS` the consumer cache refreshes; tokens with the old `kid` will then fail verification.

---

## Volumes

| Path | Purpose |
| --- | --- |
| `./keys` | EC key pair (mounted read-only into auth container) |
| `./db_data` | Persistent MariaDB data |
| `./redis/redis_data` | Persistent Redis snapshots |
| `./shared_migrations` | Alembic migration files (auto-created, shared between services) |
| `../../../auth_user_service` | Live source mount — Python changes apply without rebuild |

---

## Database isolation

This stack defaults to **Scenario 2** (per-service isolation). See the [database isolation guide](../README.md#database-isolation) for details.

---

## Common operations

```sh
# Start in background
docker compose up -d --build

# Verify JWKS endpoint — look for "kty":"EC" and "crv":"P-256"
curl http://localhost:9000/user/.well-known/jwks.json | python -m json.tool

# Follow auth service logs
docker compose logs -f auth_user_service

# Full reset
bash init.sh --reset-db
```

---

## Live testing

Run the live test suite against this stack (requires the stack to be up):

```sh
# From the repo root
pytest -m live_asymmetric --no-cov   # RS256/ES256-specific attacks (JWKS, kid confusion)
pytest -m live_stateful --no-cov     # Token revocation guarantees
pytest -m live_security --no-cov     # Universal attack categories
```

Manual smoke test:

```sh
curl http://localhost:9000/user/health/
# Expected: {"status":"ok","token_mode":"stateful","redis":"ok","database":"ok",...}

curl http://localhost:9000/user/.well-known/jwks.json
# Expected: {"keys":[{"kty":"EC","crv":"P-256","alg":"ES256","kid":"...","x":"...","y":"..."}]}
```

---

## Troubleshooting

**Auth service fails to start — key file not found** — ensure you ran `bash init.sh` and that `keys/private.pem` and `keys/public.pem` both exist.

**JWKS shows RSA key (`"kty":"RSA"`) instead of EC** — you ran `init.sh` before setting `ACCESS_TOKEN_ALGORITHM=ES256` in `auth.env`. Delete `keys/` and re-run `bash init.sh --rotate-keys`.

**JWKS endpoint returns empty `keys` array** — restart the auth service: `docker compose restart auth_user_service`.

**Consumer rejects valid tokens** — confirm `ACCESS_KEY_ID` in `auth.env` matches the `kid` in your JWTs. Also confirm `ACCESS_TOKEN_ALGORITHM=ES256` is set in `api.env`.

**`changethis` rejection on startup** — replace all `changethis` values in `auth.env`. `ACCESS_SECRET_KEY` must be absent for ES256.

---

> [Docker Compose examples](../README.md) · [Repository root](https://github.com/mano8/fa-auth-m8/tree/main)
