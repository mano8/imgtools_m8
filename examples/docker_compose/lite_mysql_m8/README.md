# local_mysql_m8

Quickest stack to get running. **MariaDB 12** + HS256 symmetric tokens + **hybrid** token mode.
No monitoring services — just the essentials for everyday development.

**Choose this when:** you want to start developing immediately without extra tooling.

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

## Setup

### 1. Copy and edit the env files

```sh
cp .env.example .env
cp auth.env.example auth.env
cp api.env.example api.env
```

Open `.env` and replace every `changethis`:

```ini
FIRST_SUPERUSER="admin@example.com"
FIRST_SUPERUSER_PASSWORD="a-strong-password"

ACCESS_SECRET_KEY="<run: python -c \"import secrets; print(secrets.token_urlsafe(64))\">"
REFRESH_SECRET_KEY="<generate>"

DB_USER="myuser"
DB_PASSWORD="<generate>"
DB_ROOT_PASSWORD="<generate>"

REDIS_PASSWORD="<generate>"
```

Open `auth.env` and replace:

```ini
PRIVATE_API_SECRET="<generate>"     # for internal service-to-service calls
TOKENS_ENCRYPTION_KEY="<generate>"  # encrypts refresh token payloads at rest
```

`api.env` requires no changes for local development.

### 2. Run init

```sh
bash init.sh
```

Generates TLS certificates for Traefik. No keys needed for HS256.

> **Windows:** `init.sh` requires bash — use **Git Bash** (included with Git for Windows) or **WSL**.

### 3. Start

```sh
docker compose up --build
```

Migrations run automatically on first boot. The superuser defined in `.env` is created
if it does not exist.

---

## Token mode: hybrid

This stack defaults to `TOKEN_MODE=hybrid`:

| Mode | Access token validated by | Refresh token | Redis round-trip per request |
| --- | --- | --- | --- |
| `stateless` | JWT signature only | JWT signature only | No |
| **`hybrid`** | **JWT signature only** | **Redis allowlist** | **No** |
| `stateful` | JWT signature + Redis blacklist | Redis allowlist | Yes |

In `hybrid` mode:

- **Login** → writes `rt:<jti>` to Redis and creates a `client_session` DB row.
- **Token refresh** → atomically rotates the Redis key and updates the DB row.
  Reuse of an old refresh token is detected immediately.
- **Logout** → deletes the Redis key and the DB row.
  The access token remains valid until it expires naturally (no server-side blacklist).

Use `stateful` mode if you need instant access token revocation on logout.

---

## URLs

All requests go through Traefik. Use port `9000` (HTTP) during development:

| What | URL |
| --- | --- |
| Auth API | `http://localhost:9000/user/` |
| Auth interactive docs | `http://localhost:9000/user/docs` |
| Auth ReDoc | `http://localhost:9000/user/redoc` |
| FastAPI service docs | `http://localhost:9000/fastapi/docs` |
| Traefik dashboard | `http://localhost:8080` |
| HTTPS | `https://localhost:4430/user/docs` (self-signed cert — accept browser warning) |

---

## Port map

| Port | Bound to | Purpose |
| --- | --- | --- |
| `8000` | `0.0.0.0` | Traefik HTTP |
| `4430` | `0.0.0.0` | Traefik HTTPS |
| `9000` | `127.0.0.1` | API services entry (set `API_BIND_IP` in `.env` to expose on LAN) |
| `8080` | `127.0.0.1` | Traefik dashboard |
| `3306` | `127.0.0.1` | MariaDB (use with any MySQL-compatible DB client) |
| `6379` | `127.0.0.1` | Redis |

---

## Configuration reference

### `.env` — shared across all services

| Variable | Default | Notes |
| --- | --- | --- |
| `TOKEN_MODE` | `hybrid` | `stateless` / `hybrid` / `stateful` |
| `ACCESS_TOKEN_ALGORITHM` | `HS256` | `HS256` for symmetric, `RS256` for asymmetric |
| `ACCESS_SECRET_KEY` | — | HMAC secret (HS256 only) |
| `REFRESH_SECRET_KEY` | — | HMAC secret for refresh tokens |
| `SELECTED_DB` | `Mysql` | `Mysql` or `Postgres` |
| `DB_HOST` | `m8_db` | Docker service name — do not change for compose |
| `FRONTEND_HOST` | `http://localhost:5173` | Added to CORS allowed origins |
| `AUTH_PREFIX` | `/user` | Path prefix consumers use to reach auth |

### `auth.env` — auth service only

| Variable | Notes |
| --- | --- |
| `PRIVATE_API_SECRET` | Secret for `X-Internal-Token` header (service-to-service calls) |
| `TOKENS_ENCRYPTION_KEY` | Fernet key for encrypting refresh token payloads in Redis |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Default: 60 min |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | Default: 3600 min (60 h) |
| `METRICS_ENABLED` | `false` — set to `true` to expose `/metrics` (needs Prometheus to be useful) |
| `AUTH_SERVICE_ROLE` | `issuer` — this service signs tokens |

### `api.env` — consumer service only

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` — verifies tokens, does not sign them |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Should match auth service value |

---

## Google OAuth (optional)

Uncomment and fill in `.env`:

```ini
GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="your-client-secret"
```

Redis is required for the OAuth code-exchange callback. This stack includes Redis,
so OAuth works out of the box once credentials are set.

---

## Volumes

| Path | Purpose |
| --- | --- |
| `./db_data` | Persistent MariaDB data |
| `./redis/redis_data` | Persistent Redis snapshots |
| `./shared_migrations` | Alembic migration files (auto-created, shared between services) |
| `../../../auth_user_service` | Live source mount — Python changes apply without rebuild |

---

## Database isolation

This stack defaults to **Scenario 2** (per-service isolation): `auth_db` and `api_db`
are created as separate databases with separate users on first volume init. To switch
to a single shared DB or add more services, see the scenario blocks in `.env.example`
and the [database isolation guide](../README.md#database-isolation).

Database provisioning runs **once** on first volume creation. If `.env` DB config
changes after the volume exists, reset with `bash init.sh --reset-db`.

---

## Common operations

```sh
# Start in background
docker compose up -d --build

# Follow logs for all services
docker compose logs -f

# Follow logs for one service
docker compose logs -f auth_user_service

# Stop (keeps volumes and data)
docker compose stop

# Stop and remove containers (keeps data volumes)
docker compose down

# Full reset — stops containers and wipes the database (prompts for confirmation)
bash init.sh --reset-db

# Rebuild one service after dependency changes
docker compose up -d --build auth_user_service
```

---

## Troubleshooting

**Services fail to start immediately** — `auth_user_service` waits for MariaDB to pass
its health check. MariaDB can take 20–30 s on first boot. Wait and watch the logs.

**`changethis` rejection on startup** — the service refuses to start if placeholder
secrets are detected. Replace all `changethis` values in `.env` and `auth.env`.

**Port conflict** — if `3306`, `6379`, or `9000` are already in use, find the process
with `netstat -ano | findstr 3306` (Windows) or `lsof -i :3306` (Mac/Linux).

**Database connection refused** — keep `DB_HOST=m8_db` in `.env`. Services reach the
database over the internal Docker network using the service name, not `localhost`.
