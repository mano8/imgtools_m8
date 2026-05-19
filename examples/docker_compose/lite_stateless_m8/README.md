# lite_stateless_m8

**MariaDB 12** + **HS256** symmetric tokens + **stateless** token mode. No monitoring services.

In stateless mode the auth service validates access tokens by checking the JWT signature only — no Redis lookup on every request. Redis is still present in this stack for login rate limiting, API key rate limiting, and refresh token management, but it is not used to blacklist access tokens.

**Choose this when:** you want the simplest token validation path and do not need instant access token revocation after logout.

---

## Summary

- [Architecture](#architecture)
- [Services](#services)
- [Limitations](#limitations)
- [Token mode: stateless](#token-mode-stateless)
- [What Redis is still used for](#what-redis-is-still-used-for)
- [Setup](#setup)
- [URLs](#urls)
- [Port map](#port-map)
- [Configuration reference](#configuration-reference)
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
       ├──► /user/*      → auth_user_service :8000  (HS256, stateless)
       └──► /fastapi/*   → fastapi_service :8000    (HS256, stateless)
                │
       ┌────────┴────────┐
       ▼                 ▼
  m8_db (MariaDB 12)  redis_cache (Redis 7.4)
                         │
                   (login rate limiting,
                    API key rate limiting,
                    refresh token store —
                    NOT used for access token blacklist)
```

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

| Limitation | Detail |
| --- | --- |
| **No access token revocation** | Logged-out access tokens remain valid until they expire. `jwt:blacklist` keys are never written in stateless mode. |
| **Google OAuth disabled** | The PKCE code-exchange flow stores a one-time code in Redis. Stateless mode does not disable Redis entirely, but `TOKEN_MODE=stateless` disables the PKCE callback. Setting `GOOGLE_CLIENT_ID` has no effect. |
| **No per-request revocation check** | Consumer services cannot detect a revoked session. A user who logs out can still present the old access token until it expires. |
| **No Prometheus / Grafana** | Use [stateful_m8](../stateful_m8/) if you need dashboards. |
| **HS256 symmetric signing** | All services share the same `ACCESS_SECRET_KEY`. Use [lite_rs256_m8](../lite_rs256_m8/) for asymmetric signing. |
| **`auth.env.example` shows `TOKEN_MODE=hybrid`** | Change it to `TOKEN_MODE=stateless` in `auth.env`. |

If you need instant revocation, switch to `TOKEN_MODE=stateful` or `TOKEN_MODE=hybrid` in `auth.env` without rebuilding (just restart the service).

---

## Token mode: stateless

| Mode | Access token validated by | Refresh token | Redis for access token | Instant revocation |
| --- | --- | --- | --- | --- |
| **`stateless`** | **JWT signature only** | **Redis allowlist** | **No** | **No** |
| `hybrid` | JWT signature only | Redis allowlist | No | No (refresh revocable) |
| `stateful` | JWT signature + Redis blacklist | Redis allowlist | Yes | Yes |

What happens during a session:

- **Login** → writes `rt:<jti>` to Redis (refresh allowlist) and creates a `client_session` DB row.
- **Token refresh** → atomically rotates the Redis key and updates the DB row. Reuse of an old refresh token is detected immediately.
- **Logout** → deletes the Redis key and the DB row. The access token is **never** added to any blacklist.
- **Request validation** → verifies HS256 signature only. No Redis lookup. No database lookup.

The `health` endpoint reports `"revocation_available": false` and `"effective_mode": "stateless"` when running in this mode.

---

## What Redis is still used for

Even with `TOKEN_MODE=stateless`, Redis handles:

| Feature | Redis keys | Behaviour when Redis is down |
| --- | --- | --- |
| Login rate limiting | `login_attempts:<email>` | Rate limiting skipped — login proceeds |
| Refresh token store | `rt:<jti>` | Refresh fails — no allowlist to check against |
| API key rate limiting | `ratelimit:<key_hash>:*` | Depends on `API_KEY_STRICT_RATE_LIMIT` setting |

Access token validation remains fully functional without Redis.

---

## Setup

### 1. Copy and edit the env files

```sh
cp auth.env.example auth.env
cp api.env.example api.env
```

Open `auth.env` and set the following (replace every `changethis`):

```ini
# Token mode — must change from the example default
TOKEN_MODE=stateless

ACCESS_TOKEN_ALGORITHM=HS256
ACCESS_SECRET_KEY="<generate>"
REFRESH_SECRET_KEY="<generate>"

FIRST_SUPERUSER="admin@example.com"
FIRST_SUPERUSER_PASSWORD="a-strong-password"

DB_PASSWORD="<generate>"
DB_ROOT_PASSWORD="<generate>"
REDIS_PASSWORD="<generate>"
PRIVATE_API_SECRET="<generate>"
TOKENS_ENCRYPTION_KEY="<generate>"
```

> **Important:** `auth.env.example` defaults to `TOKEN_MODE=hybrid`. Change it to `TOKEN_MODE=stateless`.

`api.env` requires no changes for local development.

### 2. Run init

```sh
bash init.sh
```

Generates TLS certificates for Traefik. No key pair needed for HS256.

> **Windows:** use **Git Bash** or **WSL**.

### 3. Start

```sh
docker compose up --build
```

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
| `3306` | `127.0.0.1` | MariaDB |
| `6379` | `127.0.0.1` | Redis |

---

## Configuration reference

### `auth.env` — auth service

| Variable | Value | Notes |
| --- | --- | --- |
| `TOKEN_MODE` | `stateless` | Set explicitly — example defaults to `hybrid` |
| `ACCESS_TOKEN_ALGORITHM` | `HS256` | Symmetric signing |
| `ACCESS_SECRET_KEY` | — | HMAC secret for access tokens |
| `REFRESH_SECRET_KEY` | — | HMAC secret for refresh tokens |
| `SELECTED_DB` | `Mysql` | `Mysql` or `Postgres` |
| `DB_HOST` | `m8_db` | Docker service name — do not change |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Keep short to limit post-logout exposure |
| `LOGIN_RATE_LIMIT_REQUESTS` | `5` | Max login attempts per window per email |
| `LOGIN_RATE_LIMIT_WINDOW_MINUTES` | `15` | Login rate-limit window in minutes |
| `REFRESH_RATE_LIMIT_REQUESTS` | `10` | Unused in stateless mode |
| `REFRESH_RATE_LIMIT_WINDOW_MINUTES` | `5` | Unused in stateless mode |
| `AUTH_SERVICE_ROLE` | `issuer` | Signs tokens |
| `METRICS_ENABLED` | `false` | Set to `true` to expose `/user/metrics` |

### `api.env` — consumer service

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` — verifies tokens, does not sign them |
| `TOKEN_MODE` | `stateless` — must match auth service |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Should match auth service value |

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

This stack defaults to **Scenario 2** (per-service isolation). See the [database isolation guide](../README.md#database-isolation) for details.

---

## Common operations

```sh
# Start in background
docker compose up -d --build

# Health check — confirm effective_mode is stateless
curl http://localhost:9000/user/health/

# Confirm no blacklist keys exist in Redis after logout (expected: empty or only rt:* keys)
docker compose exec redis_cache redis-cli -a "$REDIS_PASSWORD" KEYS "jwt:blacklist:*"

docker compose logs -f
bash init.sh --reset-db
```

---

## Live testing

Run the live test suite against this stack (requires the stack to be up):

```sh
# From the repo root
pytest -m live_stateless --no-cov    # Stateless mode guarantees
pytest -m live_hs256 --no-cov        # HS256-specific attacks
pytest -m live_security --no-cov     # Universal attack categories
```

Manual smoke test:

```sh
curl http://localhost:9000/user/health/
# Expected: {"status":"ok","token_mode":"stateless","effective_mode":"stateless",
#            "redis":"ok","database":"ok","revocation_available":false,...}
```

---

## Troubleshooting

**`token_mode` shows `hybrid` in health response** — `TOKEN_MODE=hybrid` is still in `auth.env`. Change it to `TOKEN_MODE=stateless` and restart: `docker compose up -d --build auth_user_service`.

**Google OAuth login page renders but callback returns 503** — Google OAuth requires Redis PKCE support, which is disabled in stateless mode. This is expected behaviour.

**`changethis` rejection on startup** — replace all `changethis` values in `auth.env`.

**Database connection refused** — keep `DB_HOST=m8_db` in `auth.env`. Services reach the database over the internal Docker network using the service name, not `localhost`.

---

> [Docker Compose examples](../README.md) · [Repository root](https://github.com/mano8/fa-auth-m8/tree/main)
