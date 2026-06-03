# postgres_m8

**PostgreSQL 16** + **HS256** symmetric tokens + **stateful** token mode. No monitoring services.

**Choose this when:** your project targets PostgreSQL and you want the auth service to match your production database engine.

---

## Summary

- [Architecture](#architecture)
- [Services](#services)
- [Limitations](#limitations)
- [Setup](#setup)
- [Token mode: stateful](#token-mode-stateful)
- [PostgreSQL vs MariaDB](#postgresql-vs-mariadb)
- [URLs](#urls)
- [Port map](#port-map)
- [Configuration reference](#configuration-reference)
- [Google OAuth](#google-oauth-optional)
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
       ├──► /user/*      → auth_user_service :8000
       └──► /fastapi/*   → fastapi_full :8000
                │
       ┌────────┴────────┐
       ▼                 ▼
  m8_db (PostgreSQL 16)  redis_cache (Redis 7.4)
```

Traefik is the single entry point. Both services run on the internal `m8_app_network` bridge and are not reachable directly from the host.

---

## Services

| Service | Image | Accessible at |
| --- | --- | --- |
| traefik | traefik:v3.3 | `:8000` (HTTP), `:4430` (HTTPS), `:9000` (API), `:8080` (dashboard) |
| m8_db | postgres:16-alpine | `127.0.0.1:5432` |
| redis_cache | redis:7.4-alpine | `127.0.0.1:6379` |
| auth_user_service | local build | via Traefik at `/user` |
| fastapi_full | local build | via Traefik at `/fastapi` |

---

## Limitations

- **No Prometheus / Grafana.** Use [metrics_m8](../metrics_m8/) if you need dashboards.
- **HS256 symmetric signing.** All services share the same secret. Use [rs256_m8](../rs256_m8/) for asymmetric signing with JWKS.
- **No Vault.** Secrets live in the `auth.env` file. Use [vault_m8](../vault_m8/) for secrets-manager integration.

---

## Setup

### 1. Copy and edit the env files

```sh
cp auth.env.example auth.env
cp api.env.example api.env
```

Open `auth.env` and replace every `changethis`:

```ini
FIRST_SUPERUSER="admin@example.com"
FIRST_SUPERUSER_PASSWORD="a-strong-password"

ACCESS_SECRET_KEY="<run: python -c \"import secrets; print(secrets.token_urlsafe(64))\">"
REFRESH_SECRET_KEY="<generate same way>"

DB_USER="auth_user"
DB_PASSWORD="<generate>"
# No DB_ROOT_PASSWORD for PostgreSQL

REDIS_PASSWORD="<generate>"

PRIVATE_API_SECRET="<generate>"     # for internal service-to-service calls
TOKENS_ENCRYPTION_KEY="<generate>"  # encrypts refresh token payloads in Redis
```

`api.env` requires no changes for local development.

### 2. Run init

```sh
bash init.sh
```

Generates TLS certificates for Traefik. No key pair needed for HS256.

> **Windows:** `init.sh` requires bash — use **Git Bash** (included with Git for Windows) or **WSL**.

### 3. Start

```sh
docker compose up --build
```

Migrations run automatically on first boot. The superuser defined in `auth.env` is created if it does not exist.

---

## Token mode: stateful

This stack defaults to `TOKEN_MODE=stateful`:

| Mode | Access token validated by | Refresh token | Redis round-trip per request |
| --- | --- | --- | --- |
| `stateless` | JWT signature only | JWT signature only | No |
| `hybrid` | JWT signature only | Redis allowlist | No |
| **`stateful`** | **JWT signature + Redis blacklist** | **Redis allowlist** | **Yes** |

What happens during a session:

- **Login** → writes `rt:<jti>` to Redis and creates a `client_session` DB row.
- **Token refresh** → atomically rotates `rt:<old_jti>` → `rt:<new_jti>` in Redis and updates the DB row.
- **Logout** → deletes `rt:<jti>`, writes `jwt:blacklist:<jti>` (TTL = remaining access token lifetime), and removes the DB session row.
- **Request validation** → checks `jwt:blacklist:<jti>` on every authenticated request.

This gives **immediate logout guarantees**: a logged-out access token is rejected on the next request, even before it expires. The trade-off is one extra Redis lookup per authenticated request.

To reduce Redis load during development, switch to `hybrid` in `auth.env`:

```ini
TOKEN_MODE=hybrid
```

---

## PostgreSQL vs MariaDB

This stack sets `SELECTED_DB=Postgres` in `auth.env`. The only differences from a MariaDB stack are:

- Connection driver (`asyncpg` / `psycopg2` vs `aiomysql` / `pymysql`)
- No `DB_ROOT_PASSWORD` — PostgreSQL uses the app user for initial setup
- `DB_PORT` defaults to `5432` and is passed explicitly to the container

To connect with a GUI client (pgAdmin, TablePlus, DBeaver), use `localhost:5432` with the `DB_USER` and `DB_PASSWORD` from `auth.env`.

---

## URLs

| What | URL |
| --- | --- |
| Auth API | `http://localhost:9000/user/` |
| Auth interactive docs | `http://localhost:9000/user/docs` |
| Auth ReDoc | `http://localhost:9000/user/redoc` |
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
| `5432` | `127.0.0.1` | PostgreSQL |
| `6379` | `127.0.0.1` | Redis |

---

## Configuration reference

### `auth.env` — auth service

| Variable | Default | Notes |
| --- | --- | --- |
| `TOKEN_MODE` | `stateful` | `stateless` / `hybrid` / `stateful` |
| `ACCESS_TOKEN_ALGORITHM` | `HS256` | `HS256` for symmetric signing |
| `ACCESS_SECRET_KEY` | — | HMAC secret (HS256 only) |
| `REFRESH_SECRET_KEY` | — | HMAC secret for refresh tokens |
| `SELECTED_DB` | `Postgres` | `Mysql` or `Postgres` |
| `DB_HOST` | `m8_db` | Docker service name — do not change for compose |
| `DB_PORT` | `5432` | PostgreSQL port |
| `FRONTEND_HOST` | `http://localhost:5173` | Added to CORS allowed origins |
| `API_PREFIX` | `/user` | URL prefix for all auth routes |
| `PRIVATE_API_SECRET` | — | Secret for `X-Internal-Token` header |
| `TOKENS_ENCRYPTION_KEY` | — | Fernet key for encrypting refresh token payloads in Redis |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | `3600` | Refresh token lifetime (60 h) |
| `LOGIN_RATE_LIMIT_REQUESTS` | `5` | Max login attempts per window per email |
| `LOGIN_RATE_LIMIT_WINDOW_MINUTES` | `15` | Login rate-limit window in minutes |
| `REFRESH_RATE_LIMIT_REQUESTS` | `10` | Max refresh rotations per window per user |
| `REFRESH_RATE_LIMIT_WINDOW_MINUTES` | `5` | Refresh rate-limit window in minutes |
| `TRUSTED_PROXY_COUNT` | `1` | Trusted proxy hops for real client IP extraction. Set to `0` if no proxy. |
| `METRICS_ENABLED` | `false` | Set to `true` to expose `/user/metrics` |
| `AUTH_SERVICE_ROLE` | `issuer` | This service signs tokens |

### `api.env` — consumer service

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` — verifies tokens, does not sign them |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Should match auth service value |

---

## Google OAuth (optional)

Uncomment and fill in `auth.env`:

```ini
GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="your-client-secret"
```

Redis is required for the OAuth code-exchange callback. This stack includes Redis, so OAuth works once credentials are set.

For Chrome extension or native-app flows (PKCE), also uncomment the optional block in `auth.env`:

```ini
GOOGLE_OAUTH_REDIRECT_URI=https://yourdomain.com/user/google-auth/oauth-callback/
OAUTH_ALLOWED_REDIRECT_SCHEMES=chrome-extension://
# OAUTH_ALLOWED_REDIRECT_PREFIXES=chrome-extension://your-extension-id.../
CORS_ALLOWED_ORIGIN_SCHEMES=chrome-extension://
```

---

## Volumes

| Path | Purpose |
| --- | --- |
| `./db_data` | Persistent PostgreSQL data |
| `./redis/redis_data` | Persistent Redis snapshots |
| `./shared_migrations` | Alembic migration files (auto-created, shared between services) |
| `../../../auth_user_service` | Live source mount — Python changes apply without rebuild |

---

## Database isolation

This stack defaults to **Scenario 2** (per-service isolation): `auth_db` and `api_db` are created as separate databases with separate users on first volume init. To switch to a single shared DB or add more services, see the scenario blocks in `auth.env.example` and the [database isolation guide](../README.md#database-isolation).

Database provisioning runs **once** on first volume creation. If DB config changes after the volume exists, reset with `bash init.sh --reset-db`.

---

## Common operations

```sh
# Start in background
docker compose up -d --build

# Follow logs for all services
docker compose logs -f

# Connect to PostgreSQL directly
docker compose exec m8_db psql -U <DB_USER> -d <DB_DATABASE>

# Inspect Redis keyspace after a login
docker compose exec redis_cache redis-cli -a "$REDIS_PASSWORD" INFO keyspace

# Stop (keeps volumes and data)
docker compose stop

# Full reset — stops containers and wipes the database (prompts for confirmation)
bash init.sh --reset-db
```

---

## Live testing

Run the live test suite against this stack (requires the stack to be up):

```sh
# From the repo root
pytest -m live_hs256 --no-cov      # HS256-specific attacks
pytest -m live_stateful --no-cov   # Token revocation guarantees
pytest -m live_security --no-cov   # Universal attack categories
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

**Services fail to start immediately** — `auth_user_service` waits for PostgreSQL to pass its health check (`pg_isready`). PostgreSQL can take 15–20 s on first boot. `fastapi_full` then waits for `auth_user_service` to pass its own health check. Watch the logs with `docker compose logs -f`.

**`changethis` rejection on startup** — replace all `changethis` values in `auth.env`.

**Port conflict on 5432** — if a local PostgreSQL instance is running, it holds port `5432`. Stop it or change `DB_PORT` in `auth.env` (e.g. to `5433`).

**Database connection refused** — keep `DB_HOST=m8_db` in `auth.env`. Services reach the database over the internal Docker network using the service name, not `localhost`.

---

> [Docker Compose examples](../README.md) · [Repository root](https://github.com/mano8/fa-auth-m8/tree/main)
