# lite_hybrid_m8

**MariaDB 12** + **RS256 asymmetric token signing** + **hybrid** token mode. No monitoring services.

This stack combines asymmetric signing (RS256 with JWKS) with the hybrid token mode. It demonstrates how to get zero-downtime key rotation and zero-round-trip access token validation at the same time — a good balance for multi-service setups where not every request needs a Redis lookup.

**Choose this when:** you want asymmetric signing with JWKS but prefer the scalability of hybrid mode over the instant-revocation guarantee of stateful mode.

---

## Summary

- [Architecture](#architecture)
- [Services](#services)
- [Limitations](#limitations)
- [Token mode: hybrid](#token-mode-hybrid)
- [How RS256 + hybrid work together](#how-rs256--hybrid-work-together)
- [Setup](#setup)
- [How JWKS works](#how-jwks-works)
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
       ├──► /user/*      → auth_user_service :8000  (RS256 issuer, hybrid mode)
       └──► /fastapi/*   → fastapi_service :8000    (RS256 consumer via JWKS, hybrid mode)
                │
       ┌────────┴────────┐
       ▼                 ▼
  m8_db (MariaDB 12)  redis_cache (Redis 7.4)
                         │
                   (refresh token store only —
                    no access token blacklist)
```

The auth service holds the **private RSA key** and issues signed tokens. Consumer services verify tokens without Redis (signature only), but refresh tokens are still managed through Redis.

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

- **Access tokens are not immediately revocable after logout.** A logged-out access token remains valid for its full remaining lifetime (default 30 min). Use [lite_rs256_m8](../lite_rs256_m8/) or [env_rs256_m8](../env_rs256_m8/) if you need instant revocation with RS256.
- **No Prometheus / Grafana.** Use [env_rs256_m8](../env_rs256_m8/) if you need dashboards.
- **No Vault.** Secrets live in `auth.env`. Use [vault_rs256_postgres_m8](../vault_rs256_postgres_m8/) for secrets-manager integration.
- **`auth.env.example` shows `TOKEN_MODE=stateful`** — the example was not updated. You must set `TOKEN_MODE=hybrid` in `auth.env` to use hybrid mode as intended.

---

## Token mode: hybrid

| Mode | Access token validated by | Refresh token | Redis for access token |
| --- | --- | --- | --- |
| `stateless` | JWT signature only | JWT signature only | No |
| **`hybrid`** | **JWT signature only** | **Redis allowlist** | **No** |
| `stateful` | JWT signature + Redis blacklist | Redis allowlist | Yes |

What happens during a session:

- **Login** → writes `rt:<jti>` to Redis and creates a `client_session` DB row.
- **Token refresh** → atomically rotates the Redis key and updates the DB row. Reuse of an old refresh token is detected immediately.
- **Logout** → deletes the Redis key and the DB row. The access token is **not** added to a blacklist — it remains valid until it expires naturally.
- **Request validation** → verifies RS256 signature only, no Redis lookup.

**Trade-off:** Consumer services can scale horizontally without Redis coordination on every request. The cost is that a revoked session's access token stays usable until it expires. Keep `ACCESS_TOKEN_EXPIRE_MINUTES` short (15–30 min) to limit the exposure window.

---

## How RS256 + hybrid work together

RS256 (asymmetric signing) and hybrid (token mode) are independent choices that compose well:

- **RS256** controls *how* the token is signed: private key on auth service, public key fetched via JWKS by consumers. Consumers can verify tokens without contacting auth.
- **Hybrid** controls *what* state is kept in Redis: only the refresh token allowlist, not an access token blacklist.

Together they give you:

- No `ACCESS_SECRET_KEY` to share between services
- Zero-downtime key rotation via JWKS
- No per-request Redis round-trip for access token validation
- Atomic refresh token rotation (replay detection)
- Google OAuth fully functional (PKCE flow uses Redis)

---

## Setup

### 1. Copy and edit the env files

```sh
cp auth.env.example auth.env
cp api.env.example api.env
```

Open `auth.env` and replace every `changethis`, then set the token mode:

```ini
# Token mode — must change from the example default
TOKEN_MODE=hybrid

ACCESS_TOKEN_ALGORITHM=RS256
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

`api.env` requires no changes (JWKS URI already points to the auth service).

> **Important:** `auth.env.example` defaults to `TOKEN_MODE=stateful`. Change it to `hybrid` to match the intent of this stack.

### 2. Generate RSA key pair + TLS certificates

```sh
bash init.sh
```

> **Windows:** use **Git Bash** or **WSL**.

This generates `keys/private.pem` and `keys/public.pem`, derives a stable `kid`, writes `ACCESS_KEY_ID` into `auth.env`, and generates the self-signed TLS certificate.

### 3. Start

```sh
docker compose up --build
```

---

## How JWKS works

```text
Consumer receives JWT with header: {"alg": "RS256", "kid": "abc123"}
         │
         ▼
Is "abc123" in local cache?
   Yes → verify signature → done (no Redis)
   No  → GET http://auth_user_service:8000/user/.well-known/jwks.json
              │
              ▼  (returns public keys indexed by kid)
         Cache result for JWKS_CACHE_TTL_SECONDS (default: 300 s)
         Verify signature → done
```

The JWKS endpoint (no auth required):

```text
http://localhost:9000/user/.well-known/jwks.json
```

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
| `TOKEN_MODE` | `hybrid` | Set explicitly — example defaults to `stateful` |
| `ACCESS_TOKEN_ALGORITHM` | `RS256` | Asymmetric signing |
| `REFRESH_TOKEN_ALGORITHM` | `HS256` | Refresh tokens remain symmetric |
| `ACCESS_PRIVATE_KEY_FILE` | `/opt/keys/private.pem` | RSA private key inside the container |
| `ACCESS_PUBLIC_KEY_FILE` | `/opt/keys/public.pem` | RSA public key inside the container |
| `ACCESS_KEY_ID` | — | Stable `kid` written by `init.sh` |
| `REFRESH_SECRET_KEY` | — | HMAC secret for refresh tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Keep short to limit post-logout window |
| `LOGIN_RATE_LIMIT_REQUESTS` | `5` | Max login attempts per window per email |
| `LOGIN_RATE_LIMIT_WINDOW_MINUTES` | `15` | Login rate-limit window in minutes |
| `REFRESH_RATE_LIMIT_REQUESTS` | `10` | Max refresh rotations per window per user |
| `REFRESH_RATE_LIMIT_WINDOW_MINUTES` | `5` | Refresh rate-limit window in minutes |
| `AUTH_SERVICE_ROLE` | `issuer` | Signs tokens with the RSA private key |

### `api.env` — consumer service

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` — verifies tokens via JWKS, does not sign them |
| `TOKEN_MODE` | `hybrid` — must match auth service |
| `JWKS_URI` | `http://auth_user_service:8000/user/.well-known/jwks.json` |
| `JWKS_CACHE_TTL_SECONDS` | `300` |

---

## Key rotation

```sh
# 1. Regenerate the RSA key pair and update ACCESS_KEY_ID
bash init.sh --rotate-keys

# 2. Restart the auth service
docker compose up -d --build auth_user_service

# 3. Consumers self-update — no restart needed
```

---

## Volumes

| Path | Purpose |
| --- | --- |
| `./keys` | RSA key pair (mounted read-only into auth container) |
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

# Verify JWKS endpoint
curl http://localhost:9000/user/.well-known/jwks.json | python -m json.tool

# Inspect Redis — should only contain refresh token keys (no blacklist keys in hybrid mode)
docker compose exec redis_cache redis-cli -a "$REDIS_PASSWORD" KEYS "*"

docker compose logs -f auth_user_service
bash init.sh --reset-db
```

---

## Live testing

Run the live test suite against this stack (requires the stack to be up):

```sh
# From the repo root
pytest -m live_asymmetric --no-cov   # RS256/ES256-specific attacks
pytest -m live_hybrid --no-cov       # Hybrid mode behaviour (no access token blacklist)
pytest -m live_security --no-cov     # Universal attack categories
```

Manual smoke test:

```sh
curl http://localhost:9000/user/health/
# Expected: {"status":"ok","token_mode":"hybrid","redis":"ok","database":"ok",...}
```

---

## Troubleshooting

**`token_mode` shows `stateful` in health response** — `TOKEN_MODE=stateful` is still in `auth.env`. Change it to `hybrid` and restart: `docker compose up -d --build auth_user_service`.

**Auth service fails to start — key file not found** — run `bash init.sh` to generate the key pair.

**JWKS endpoint returns empty `keys` array** — restart: `docker compose restart auth_user_service`.

**`changethis` rejection** — replace all `changethis` values in `auth.env`. `ACCESS_SECRET_KEY` must be absent for RS256.

---

> [Docker Compose examples](../README.md) · [Repository root](https://github.com/mano8/fa-auth-m8/tree/main)
