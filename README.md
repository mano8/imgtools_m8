# fa-auth-m8

![CI/CD](https://github.com/mano8/fa-auth-m8/actions/workflows/CI.yaml/badge.svg?branch=main)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/edab51cc8805468fb3884e1d9e57ccdc)](https://app.codacy.com/gh/mano8/fa-auth-m8/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![codecov](https://codecov.io/gh/mano8/fa-auth-m8/graph/badge.svg?token=LH7GTT2JZY)](https://codecov.io/gh/mano8/fa-auth-m8)

A self-contained FastAPI authentication microservice designed to run as a Docker container via Docker Compose. It provides JWT-based authentication, Google OAuth2, session management, user management, API key management, and private inter-service endpoints for any project in the m8 stack.

---

## Summary

- [Features](#features)
- [Architecture](#architecture)
- [Docker Compose Stacks](#docker-compose-stacks)
- [API Endpoints](#api-endpoints)
- [Quick Start](#quick-start)
- [Choosing a Database](#choosing-a-database)
- [Environment Variables](#environment-variables)
- [Infrastructure Resilience](#infrastructure-resilience)
- [Deployment Modes](#deployment-modes)
- [API Key Authentication](#api-key-authentication)
- [Private API](#private-api)
- [Consumer Service Integration](#consumer-service-integration)
- [Development](#development)
- [Prometheus Metrics](#prometheus-metrics)
- [Dependencies](#dependencies)

---

## Features

- Email/password login with bcrypt password hashing (timing-attack safe)
- Google OAuth2 login with PKCE
- JWT access + refresh token pair (refresh token in HttpOnly cookie, atomically rotated on every use)
- RS256 / ES256 asymmetric signing with JWKS endpoint for zero-downtime key rotation
- Opt-in `iss`/`aud` JWT claim enforcement to prevent cross-service token reuse
- Session tracking and JTI revocation via Redis
- Login rate limiting per email (Redis-backed, namespace-hardened)
- **API key authentication** with per-key fixed-window rate limiting (MINUTE / HOUR / DAY / MONTH), `X-RateLimit-*` response headers, and write-behind `last_used_at` tracking
- Role-based access control (`user`, `admin`, `superuser`)
- User management CRUD (superuser only)
- Profile self-service (read, update, password change, delete account, avatar upload)
- Dashboard activity endpoints
- Private inter-service API (protected by shared secret + Docker network isolation)
- MySQL **or** PostgreSQL — switchable via a single env var
- Prometheus metrics (`METRICS_ENABLED=true`) with API key–specific counters and alert rules
- Alembic migrations auto-applied on first start
- VS Code remote debugger support

---

## Architecture

```text
                        Internet
                           │
                    ┌──────▼──────┐
                    │   Traefik   │  TLS termination, IP forwarding
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼──────┐  ┌──────▼──────┐  ┌─────▼──────┐
   │ auth-service│  │  consumer   │  │  Prometheus │
   │  :8000      │  │  service    │  │  + Grafana  │
   └──┬──────┬───┘  └─────────────┘  └────────────┘
      │      │
┌─────▼──┐ ┌─▼──────────┐
│ MySQL/ │ │ Redis :6379 │
│ Postgres│ └────────────┘
└────────┘
```

Other services on the same Docker network call the private API at `http://auth-service:8000/user/private/`.

---

## Docker Compose Stacks

Ten ready-to-run stacks are provided under [`examples/docker_compose/`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose). See the [stack selection guide](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose#which-stack-should-i-use) for help choosing.

| Stack | Database | Algorithm | Token mode | Observability | Notes |
| ----- | -------- | --------- | ---------- | ------------- | ----- |
| [`lite_mysql_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/lite_mysql_m8) | MariaDB | HS256 | `hybrid` | — | Fastest start |
| [`lite_postgres_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/lite_postgres_m8) | PostgreSQL 16 | HS256 | `stateful` | — | PostgreSQL variant |
| [`lite_rs256_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/lite_rs256_m8) | MariaDB | RS256 | `stateful` | — | Asymmetric signing + JWKS |
| [`lite_es256_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/lite_es256_m8) | MariaDB | ES256 | `stateful` | — | ECDSA asymmetric signing |
| [`lite_hybrid_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/lite_hybrid_m8) | MariaDB | RS256 | `hybrid` | — | RS256 + hybrid mode |
| [`lite_stateless_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/lite_stateless_m8) | MariaDB | HS256 | `stateless` | — | No Redis for JWT validation |
| [`stateful_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/stateful_m8) | MariaDB | HS256 | `stateful` | Prometheus + Grafana | Full stateful stack + metrics |
| [`RS256_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/RS256_m8) | MariaDB | RS256 | `stateful` | Prometheus + Grafana | RS256 + JWKS + metrics |
| [`vault_rs256_postgres_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/vault_rs256_postgres_m8) | PostgreSQL 16 | RS256 | `stateful` | Prometheus + Grafana | HashiCorp Vault + hardened |
| [`template`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/template) | configurable | configurable | configurable | — | Bare template for new stacks |

**Start here →** [`lite_mysql_m8`](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose/lite_mysql_m8) for the fastest path to a running stack.

---

## API Endpoints

All routes are prefixed with `API_PREFIX` (default `/user`).

| Tag | Method | Path | Auth | Description |
| --- | ------ | ---- | ---- | ----------- |
| health | GET | `/health/` | — | Redis, database, effective token mode |
| jwks | GET | `/.well-known/jwks.json` | — | JWKS endpoint (RS256/ES256 public key; `{"keys":[]}` for HS256) |
| login | POST | `/login/access-token` | — | Email/password login — returns access token, sets refresh cookie |
| login | POST | `/login/refresh-token/` | — | Refresh access token from HttpOnly cookie |
| login | POST | `/login/logout/` | JWT | Revoke session, blacklist JTI, clear cookie |
| login | POST | `/login/test-token/` | JWT | Validate access token, return current user |
| google-api | GET | `/google-api/login/` | — | Render Google login page |
| google-api | GET | `/google-api/login_success/{session_id}/` | JWT cookie | Render OAuth success page |
| google-auth | GET | `/google-auth/oauth-callback/` | — | Google OAuth2 PKCE callback — exchange code, create/update user |
| profile | GET | `/profile/get/me/` | JWT | Read own profile |
| profile | PATCH | `/profile/update/me/` | JWT | Update own profile |
| profile | PATCH | `/profile/me/password/` | JWT | Change own password |
| profile | POST | `/profile/upload_avatar/` | JWT | Upload profile avatar |
| profile | DELETE | `/profile/delete/me/` | JWT | Delete own account |
| api-keys | GET | `/profile/api-keys/verify` | X-API-Key | Validate key header, enforce rate limits, return key metadata |
| api-keys | POST | `/profile/api-keys/` | JWT | Create API key — plaintext returned once, never stored |
| api-keys | GET | `/profile/api-keys/` | JWT | List own API keys (metadata only) |
| api-keys | GET | `/profile/api-keys/{key_id}` | JWT | Get single key metadata |
| api-keys | DELETE | `/profile/api-keys/{key_id}` | JWT | Revoke API key |
| sessions | GET | `/sessions/` | superuser | List all sessions (paginated) |
| sessions | GET | `/sessions/get/{session_id}/` | superuser | Get session by ID |
| sessions | GET | `/sessions/get-by-user/{user_id}/` | superuser | Get session by user ID |
| sessions | GET | `/sessions/get-current/` | JWT | Get own current session |
| sessions | POST | `/sessions/refresh-google-tokens/` | JWT | Refresh external Google tokens |
| sessions | DELETE | `/sessions/delete-by-user/{user_id}/` | superuser | Delete all sessions for a user |
| sessions | DELETE | `/sessions/delete/{session_id}/` | superuser | Delete specific session |
| users | GET | `/users/` | superuser | List all users (paginated) |
| users | POST | `/users/new_user/` | superuser | Create user with password |
| users | POST | `/users/signup/` | superuser | Register user (no password set) |
| users | GET | `/users/get/{user_id}/` | superuser | Get user by ID |
| users | PATCH | `/users/update/{user_id}/` | superuser | Update user |
| users | DELETE | `/users/delete/{user_id}/` | superuser | Delete user |
| dashboard | GET | `/dashboard/users/activity/` | JWT | All-user activity stats (monthly) |
| dashboard | GET | `/dashboard/users/activity/current/` | JWT | Own activity stats (monthly) |
| metrics | GET | `/metrics` | — | Prometheus metrics (`METRICS_ENABLED=true` only) |
| private | POST | `/private/users/` | X-Internal-Token | Create user (inter-service, Docker network only) |

Interactive docs at `{BACKEND_HOST}{API_PREFIX}/docs` when `SET_DOCS=true`.

---

## Quick Start

### 1. Choose a stack

```bash
cd examples/docker_compose/lite_mysql_m8      # fastest start — HS256 + hybrid mode
# or
cd examples/docker_compose/lite_rs256_m8      # asymmetric RS256 + JWKS
```

See the [Docker Compose stack guide](https://github.com/mano8/fa-auth-m8/tree/main/examples/docker_compose) to pick the right stack.

### 2. Copy env files and generate secrets

```bash
cp .env.example .env
cp auth.env.example auth.env
cp api.env.example api.env
# Fill in all `changethis` values in .env and auth.env
```

Generate secrets with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 3. Generate keys and TLS certificate

```bash
bash init.sh
# RS256/ES256 stacks: also generates the key pair and writes ACCESS_KEY_ID
```

> **Windows:** use **Git Bash** (included with Git for Windows) or **WSL**.

### 4. Start the stack

```bash
docker compose up --build
```

Alembic migrations run automatically. The first start seeds the superuser from `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`.

### 5. Verify

```http
GET http://localhost:9000/user/health/
```

---

## Choosing a Database

Set `SELECTED_DB` in `.env` (or `auth.env`):

| Value | Driver | Default port |
| ----- | ------ | ------------ |
| `Mysql` (default) | `pymysql` / `aiomysql` | 3306 |
| `Postgres` | `psycopg2` / `asyncpg` | 5432 |

---

## Environment Variables

### Core

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `DOMAIN` | yes | — | Public domain (e.g. `localhost`) |
| `ENVIRONMENT` | yes | — | `local` \| `development` \| `staging` \| `production` |
| `API_PREFIX` | yes | `/user` | URL prefix for all routes |
| `PROJECT_NAME` | yes | — | Project name shown in docs |
| `STACK_NAME` | yes | — | Docker Compose stack slug |
| `BACKEND_HOST` | yes | — | Full backend URL (e.g. `http://127.0.0.1:9000`) |
| `FRONTEND_HOST` | yes | — | Full frontend URL (e.g. `http://localhost:5173`) |
| `BACKEND_CORS_ORIGINS` | yes | — | Comma-separated allowed origins |
| `TABLES_PREFIX` | no | `auth` | DB table name prefix (e.g. `auth_user`, `auth_api_key`) |
| `SET_DOCS` | no | `true` | Enable Swagger UI at `{API_PREFIX}/docs` |
| `SET_REDOC` | no | `true` | Enable ReDoc at `{API_PREFIX}/redoc` |

### Tokens

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `TOKEN_MODE` | no | `stateful` | `stateless` \| `hybrid` \| `stateful` — controls Redis usage and JTI revocation |
| `ACCESS_TOKEN_ALGORITHM` | no | `HS256` | Signing algorithm for access tokens (`HS256`, `RS256`, `ES256`) |
| `REFRESH_TOKEN_ALGORITHM` | no | `HS256` | Signing algorithm for refresh tokens |
| `ACCESS_SECRET_KEY` | HS256 only | — | Symmetric signing key for access tokens |
| `REFRESH_SECRET_KEY` | yes | — | Signing key for refresh tokens (always HS256) |
| `ACCESS_PRIVATE_KEY_FILE` | RS256/ES256 only | — | Path to PEM private key file (mounted into container) |
| `ACCESS_PUBLIC_KEY_FILE` | RS256/ES256 only | — | Path to PEM public key file (distributed to consumers) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | no | `120` | Refresh token lifetime |
| `REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS` | no | `3600` | Refresh cookie max-age |
| `TOKENS_ENCRYPTION_KEY` | yes | — | Key for `SessionMiddleware` cookie signing |
| `TOKEN_ISSUER` | no | — | When set, embeds `iss` in tokens and requires a match on validation |
| `TOKEN_AUDIENCE` | no | — | When set, embeds `aud` in tokens and requires a match on validation |
| `ACCESS_KEY_ID` | no | — | Explicit `kid` in JWT headers and JWKS; auto-derived from key fingerprint when unset |
| `AUTH_SERVICE_ROLE` | no | `issuer` | `issuer` (auth service) or `consumer` (downstream services) |
| `JWKS_URI` | no | — | Consumer services: JWKS endpoint URL; enables automatic `JwksKeyResolver` wiring |
| `JWKS_CACHE_TTL_SECONDS` | no | `300` | JWKS key cache TTL in seconds |

**HS256 (default)** — set `ACCESS_SECRET_KEY` and `REFRESH_SECRET_KEY`; leave asymmetric key vars blank.

**RS256 / ES256** — set `ACCESS_TOKEN_ALGORITHM`, `ACCESS_PRIVATE_KEY_FILE`, `ACCESS_PUBLIC_KEY_FILE`. Mount the key files into the container (see `examples/docker_compose/RS256_m8/keys/`). Generate a key pair:

```bash
# RS256
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem

# ES256
openssl ecparam -genkey -name prime256v1 -noout -out private.pem
openssl ec -in private.pem -pubout -out public.pem
```

Or use `bash init.sh` in any asymmetric stack — it generates the correct key type automatically.

### Database

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `SELECTED_DB` | no | `Mysql` | `Mysql` or `Postgres` |
| `DB_HOST` | yes | — | Database host |
| `DB_PORT` | yes | — | Database port |
| `DB_DATABASE` | yes | — | Database name |
| `DB_USER` | yes | — | Database user |
| `DB_PASSWORD` | yes | — | Database password |

### Redis

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `REDIS_HOST` | yes | Redis host |
| `REDIS_PORT` | yes | Redis port |
| `REDIS_USER` | yes | Redis user |
| `REDIS_PASSWORD` | yes | Redis password |

### Auth & OAuth

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `FIRST_SUPERUSER` | yes | Email of the bootstrap superuser — used only on first run |
| `FIRST_SUPERUSER_PASSWORD` | yes | Password of the bootstrap superuser — used only on first run |
| `GOOGLE_CLIENT_ID` | no | Google OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | no | Google OAuth2 client secret |
| `PRIVATE_API_SECRET` | yes | Shared secret for `X-Internal-Token` header |

### API Key Rate Limiting

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `API_KEY_STRICT_RATE_LIMIT` | no | `false` | When `true`, return 503 instead of allowing requests when Redis is unavailable |
| `API_KEY_DEFAULT_LIMIT_MINUTE` | no | `60` | Default requests per minute (`0` = disabled) |
| `API_KEY_DEFAULT_LIMIT_HOUR` | no | `1000` | Default requests per hour |
| `API_KEY_DEFAULT_LIMIT_DAY` | no | `10000` | Default requests per day |
| `API_KEY_DEFAULT_LIMIT_MONTH` | no | `200000` | Default requests per month |
| `API_KEY_MAX_PER_USER` | no | `10` | Maximum API keys a user may create |

### Observability

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `METRICS_ENABLED` | no | `false` | Expose `GET /metrics` Prometheus endpoint |
| `METRICS_GROUPS` | no | `all` | Comma-separated groups: `all` \| `traffic` \| `performance` \| `reliability` \| `health` \| `auth` |
| `SENTRY_DSN` | no | — | Sentry DSN for error tracking |

### Deployment

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `API_BIND_IP` | `127.0.0.1` | Host IP Traefik binds port 9000 to. Set to `0.0.0.0` for LAN/public exposure |
| `TRUSTED_PROXY_IPS` | `172.16.0.0/12` | CIDR(s) Uvicorn trusts as reverse-proxy source for `X-Forwarded-For` |
| `STRICT_PRODUCTION_MODE` | `false` | When `true`, enforce production-grade checks (e.g. secure cookies) even in non-production environments |

### Static / Templates

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `STATIC_BASE_PATH` | yes | Absolute path to static files directory |
| `TEMPLATES_BASE_PATH` | yes | Absolute path to Jinja2 templates directory |

---

## Infrastructure Resilience

The service degrades gracefully when Redis or the database is temporarily unavailable.

### Redis unavailable

| `TOKEN_MODE` | Login | Refresh | Logout | Google OAuth |
| ------------ | ----- | ------- | ------ | ------------ |
| `stateless` | ✅ unaffected | ✅ unaffected | ✅ unaffected | ❌ 503 (PKCE requires Redis) |
| `hybrid` | ✅ works, rate limiting skipped | ✅ works, JTI check skipped | ✅ works | ❌ 503 |
| `stateful` | ✅ works, rate limiting skipped | ✅ works, JTI allowlist check skipped | ✅ works | ❌ 503 |

In `stateful`/`hybrid` mode with Redis down, the `/health/` endpoint reflects `effective_mode: stateless_degraded` and a `CRITICAL` log is emitted at startup.

API key rate limiting: when Redis is unavailable and `API_KEY_STRICT_RATE_LIMIT=false` (default), requests are allowed through. With `API_KEY_STRICT_RATE_LIMIT=true`, the endpoint returns 503.

### Database unavailable

All routes that touch the database return `503 Service Unavailable` with a clear message.

### Health endpoint

```http
GET {API_PREFIX}/health/
```

```json
{
  "status": "ok",
  "token_mode": "stateful",
  "effective_mode": "stateful",
  "redis": "ok",
  "database": "ok",
  "revocation_available": true,
  "rate_limiting_available": true,
  "degraded_since": null
}
```

`degraded_since` is the UTC timestamp when Redis first became unreachable in the current process lifetime, or `null` when healthy.

---

## Deployment Modes

| Mode | `API_BIND_IP` | TLS | HSTS | Use when |
| ---- | ------------- | --- | ---- | -------- |
| **Development** | `0.0.0.0` | self-signed OK | off | local machine, Docker dev loop |
| **Private LAN / homelab** | `0.0.0.0` or `127.0.0.1` | local CA recommended | off | Raspberry Pi, NAS, private LAN |
| **Public / production** | `127.0.0.1` | valid cert required | on (opt-in) | VPS, cloud, internet-facing |

### Running behind a reverse proxy (real client IP)

Requires a coordinated three-layer setup:

1. **Traefik** — add `forwardedHeaders.trustedIPs` to each entrypoint in `traefik.yml` (strips client-supplied `X-Forwarded-For`, prevents IP spoofing).
2. **Uvicorn** — the startup script reads `TRUSTED_PROXY_IPS` (default `172.16.0.0/12`) and passes it via `--proxy-headers --forwarded-allow-ips`. Never use `*`.
3. **Application** — `_client_ip()` reads the leftmost `X-Forwarded-For` value, which is trustworthy only because layers 1 and 2 have been configured.

### HSTS (opt-in, public deployments only)

`Strict-Transport-Security` is commented out in all `traefik/dynamic_conf.yml` files. Uncomment after confirming TLS is stable and the hostname will remain HTTPS-only for the full `stsSeconds` period.

---

## API Key Authentication

API keys are created by authenticated users and validated by consumer services via the `GET /profile/api-keys/verify` endpoint (or the `get_current_api_key` FastAPI dependency in the SDK).

### Key lifecycle

- Created with `POST /profile/api-keys/` — plaintext key returned **once only**, never stored.
- Stored as a SHA-256 hash in the database alongside metadata (name, expiry, revocation flag).
- `last_used_at` is updated via a Redis write-behind queue flushed every 60 seconds.
- Revoked with `DELETE /profile/api-keys/{key_id}`.

### Rate limiting

Each key is checked against up to four fixed windows (MINUTE, HOUR, DAY, MONTH). Priority chain: per-key `RateLimit` rows → per-user defaults → `API_KEY_DEFAULT_LIMIT_*` settings.

Response headers on every API key request:

| Header | Description |
| ------ | ----------- |
| `X-RateLimit-Limit` | Limit for the tightest (MINUTE) window |
| `X-RateLimit-Remaining` | Remaining requests in the MINUTE window |
| `X-RateLimit-Reset` | Unix timestamp when the MINUTE window resets |
| `Retry-After` | Seconds to wait (429 responses only) |

---

## Private API

Endpoints under `/user/private/` are for inter-service calls only:

- Must not be exposed to the public internet — enforce at the reverse proxy / Docker network level.
- Every request must include `X-Internal-Token: <PRIVATE_API_SECRET>`.

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/private/users/` | Create a user account (called by other microservices) |

---

## Consumer Service Integration

`examples/fastapi_service` is a reference implementation showing how a downstream microservice integrates with `auth_user_service` using `auth-sdk-m8`.

### Token validation

```python
from auth_sdk_m8.security import build_access_validator, ValidationHooks

_validator = build_access_validator(settings, hooks=_hooks)
```

`build_access_validator` reads `ACCESS_TOKEN_ALGORITHM`, `ACCESS_SECRET_KEY` / `ACCESS_PUBLIC_KEY_FILE`, `TOKEN_ISSUER`, `TOKEN_AUDIENCE`, and `JWKS_URI` directly from a `CommonSettings` instance.

### JWKS-based key validation (RS256/ES256)

When `JWKS_URI` is set, `build_access_validator` wires up `JwksKeyResolver` automatically. The resolver fetches `/.well-known/jwks.json`, caches keys by `kid`, and refreshes on cache miss — supporting zero-downtime key rotation.

```ini
ACCESS_TOKEN_ALGORITHM=RS256
JWKS_URI=http://auth-service/user/.well-known/jwks.json
JWKS_CACHE_TTL_SECONDS=300
```

### Revocation check (stateful mode)

Consumer services must share the same Redis instance and set `TOKEN_MODE="stateful"`.

```python
from auth_sdk_m8.security import AccessTokenBlacklist

if settings.TOKEN_MODE == "stateful" and redis is not None:
    if AccessTokenBlacklist(redis).is_revoked(payload.jti):
        raise HTTPException(status_code=403, detail="Token has been revoked.")
```

### Issuer / audience enforcement (opt-in)

Set `TOKEN_ISSUER` and `TOKEN_AUDIENCE` to the **same values** in both the auth service and every consumer. When set, the auth service embeds `iss`/`aud` claims in issued tokens and all validators require an exact match.

---

## Development

### Run locally (without Docker)

```bash
cd auth_user_service
pip install -r requirements_base.txt -r requirements_dev.txt
uvicorn auth_user_service.main:app --host 0.0.0.0 --port 8000 --reload
```

### VS Code remote debugging

Set `VSCODE_DEBUG=true` in the container environment. The startup script launches `debugpy` on port `5678` and waits for the debugger to attach before starting Uvicorn.

### Database migrations

Migrations are applied automatically on container start. To run manually:

```bash
alembic -c auth_user_service/alembic.ini revision --autogenerate -m "description"
alembic -c auth_user_service/alembic.ini upgrade head
```

### Linting & formatting

```bash
ruff format .
ruff check .
ruff check . --fix
```

### Tests

```bash
# Unit + integration tests (default — no live stack required)
pytest

# All live tests against a running stack
pytest -m live --no-cov

# Target a specific algorithm or token mode
pytest tests/live/test_security_universal.py --no-cov   # any stack
pytest -m live_asymmetric --no-cov                      # RS256 / ES256 stacks
pytest -m live_hs256 --no-cov                           # HS256 stacks
pytest -m live_stateful --no-cov                        # TOKEN_MODE=stateful
pytest -m live_hybrid --no-cov                          # TOKEN_MODE=hybrid
pytest -m live_stateless --no-cov                       # TOKEN_MODE=stateless
```

The live suite is modular — each file carries a `require_algorithm` / `require_token_mode` mark so tests are automatically skipped when the running stack does not match. `conftest.py` auto-detects the stack's algorithm and token mode at session start.

| Module | Mark | Covers |
| ------ | ---- | ------- |
| `test_security_universal.py` | `live_security` | 13 attack categories (A–M): brute-force, JWT forgery, IDOR, rate-limit bypass, CORS, private API exposure, file upload, info disclosure, HTTP headers, cookie security, API key abuse |
| `test_asymmetric.py` | `live_asymmetric` | alg=none confusion, JWKS exposure, attacker-generated key — RS256 / ES256 only |
| `test_hs256.py` | `live_hs256` | HS256-specific attacks |
| `test_stateful.py` | `live_stateful` | Token revocation, session-chain invalidation |
| `test_hybrid.py` | `live_hybrid` | Partial-Redis degraded mode behaviour |
| `test_stateless.py` | `live_stateless` | No-Redis guarantees |

The `tests/security/` unit suite (no live stack required) covers JWT security, Redis resilience, refresh lifecycle, input sanitisation, JWKS endpoint, OAuth adversarial, iss/aud validation, session-chain invalidation, exception handling, and client IP attribution.

---

## Prometheus Metrics

Enabled with `METRICS_ENABLED=true`. The metric prefix is derived from `API_PREFIX` (e.g. `/user` → `user_`).

| Group | Metric | Type | Labels |
| ----- | ------ | ---- | ------ |
| traffic | `{prefix}http_requests_total` | Counter | method, endpoint, status_code |
| performance | `{prefix}http_request_duration_seconds` | Histogram | method, endpoint |
| reliability | `{prefix}http_errors_total` | Counter | method, endpoint, status_class |
| health | `{prefix}http_status_total` | Counter | status_code |
| auth | `{prefix}auth_login_attempts_total` | Counter | result: success \| wrong_credentials \| inactive_user \| rate_limited |
| auth | `{prefix}auth_token_refresh_total` | Counter | result: success \| invalid \| revoked |
| auth | `{prefix}auth_logout_total` | Counter | — |
| auth | `{prefix}auth_token_validation_failures_total` | Counter | reason: invalid \| revoked \| inactive |
| auth | `{prefix}auth_oauth_attempts_total` | Counter | provider, result: success \| failed |
| auth | `{prefix}auth_api_key_validations_total` | Counter | result: success \| invalid \| revoked \| expired |
| auth | `{prefix}auth_api_key_rate_limit_checks_total` | Counter | result: checked \| allowed \| blocked |
| auth | `{prefix}auth_api_key_rate_limit_hits_total` | Counter | period: minute \| hour \| day \| month |
| auth | `{prefix}auth_api_key_lifecycle_total` | Counter | action: created \| revoked |
| auth | `{prefix}auth_api_key_flush_duration_seconds` | Histogram | — |

Alert rules for `stateful_m8`, `RS256_m8`, and `vault_rs256_postgres_m8` stacks (`prometheus/alerts.yml`):

- `ApiKeyBlockRatioHigh` — hits/checks > 10% over 5 min
- `ApiKeyRateLimitInvariantViolation` — hits > checks × 1.1 (instrumentation sanity guard)
- `ApiKeyFlushLatencyHigh` — p99 flush latency > 500 ms
- `ApiKeyHighInvalidRate` — > 1 invalid/revoked/expired key/s over 5 min

---

## Dependencies

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/) + [Alembic](https://alembic.sqlalchemy.org/)
- [auth-sdk-m8](https://github.com/mano8/auth-sdk-m8) — shared schemas, JWT validation, refresh token rotation, JWKS resolver, base controllers
- [Redis](https://redis.io/) — session revocation, refresh token allowlist, rate limiting, PKCE store, write-behind queue
- [PyJWT](https://pyjwt.readthedocs.io/) + [passlib](https://passlib.readthedocs.io/) + [cryptography](https://cryptography.io/)
- [google-auth](https://google-auth.readthedocs.io/) — Google OAuth2

---

## License

MIT © Eli Serra
