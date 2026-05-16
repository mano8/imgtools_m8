# fa-auth-m8

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/edab51cc8805468fb3884e1d9e57ccdc)](https://app.codacy.com/gh/mano8/fa-auth-m8/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![codecov](https://codecov.io/gh/mano8/fa-auth-m8/graph/badge.svg?token=LH7GTT2JZY)](https://codecov.io/gh/mano8/fa-auth-m8)

A self-contained FastAPI authentication microservice designed to run as a Docker container via Docker Compose. It provides JWT-based authentication, Google OAuth2, session management, user management, and private inter-service endpoints for any project in the m8 stack.

---

## Features

- Email/password login with bcrypt password hashing (timing-attack safe)
- Google OAuth2 login with PKCE
- JWT access + refresh token pair (refresh token in HttpOnly cookie, atomically rotated on every use)
- RS256 / ES256 asymmetric signing with JWKS endpoint for zero-downtime key rotation
- Opt-in `iss`/`aud` JWT claim enforcement to prevent cross-service token reuse
- Session tracking and JTI revocation via Redis
- Login rate limiting per email (Redis-backed, namespace-hardened)
- Role-based access control (`user`, `admin`, `superuser`)
- User management CRUD (superuser only)
- Dashboard activity endpoints
- Private inter-service API (protected by shared secret + Docker network isolation)
- MySQL **or** PostgreSQL — switchable via a single env var
- Prometheus metrics (`METRICS_ENABLED=true`)
- Alembic migrations auto-applied on first start
- VS Code remote debugger support

---

## Architecture

```
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

Four ready-to-run stacks are provided under `examples/docker_compose/`:

| Stack | Database | Token mode | Notes |
| ----- | -------- | ---------- | ----- |
| `local_mysql_m8` | MariaDB | `stateful` (HS256) | Simplest starting point |
| `dev_postgres_m8` | PostgreSQL 16 | `stateful` (HS256) | PostgreSQL variant with Traefik |
| `stateful_m8` | MariaDB | `stateful` (HS256) | + Prometheus + Grafana |
| `RS256_m8` | MariaDB | `hybrid` (RS256) | Asymmetric signing + JWKS + Prometheus + Grafana |

Each stack ships its own `example.env.txt`, `traefik/`, and Alembic migrations.

---

## API Endpoints

All routes are prefixed with `API_PREFIX` (default `/user`).

| Tag | Method | Path | Description |
| --- | ------ | ---- | ----------- |
| health | GET | `/health/` | Service health — Redis, database, effective token mode (no auth required) |
| login | POST | `/login/access-token` | Email/password login — returns access token, sets refresh cookie |
| login | POST | `/login/refresh-token/` | Refresh access token from cookie |
| login | POST | `/login/logout/` | Revoke session and clear cookie |
| login | POST | `/login/test-token/` | Validate access token |
| jwks | GET | `/.well-known/jwks.json` | JWKS endpoint (RS256/ES256 public key; `{"keys":[]}` for HS256) |
| oauth-login | * | `/oauth/...` | OAuth2 password-flow endpoints |
| google-auth | GET | `/google/login` | Initiate Google OAuth2 flow |
| google-auth | GET | `/google/callback` | Google OAuth2 callback |
| profile | GET/PATCH | `/profile/me` | Read/update own profile |
| profile | POST | `/profile/me/avatar` | Upload profile avatar |
| sessions | GET/DELETE | `/sessions/...` | List and revoke own sessions |
| users | GET/POST/PATCH/DELETE | `/users/...` | User management (superuser only) |
| dashboard | GET | `/dashboard/users/activity/` | User activity stats (superuser only) |
| metrics | GET | `/metrics` | Prometheus metrics (`METRICS_ENABLED=true` only) |
| private | * | `/private/...` | Inter-service endpoints — Docker network + `X-Internal-Token` header |

Interactive docs at `{BACKEND_HOST}{API_PREFIX}/docs` when `SET_DOCS=true`.

---

## Quick Start

### 1. Choose a stack and copy the env file

```bash
cd examples/docker_compose/stateful_m8
cp example.env.txt .env
# edit .env — fill in all required values
```

### 2. Start the stack

```bash
docker compose up --build
```

Alembic migrations run automatically. The first start also seeds the superuser defined by `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`.

### 3. Verify

```http
GET http://localhost:9000/user/health/
```

---

## Choosing a Database

Set `SELECTED_DB` in `.env`:

| Value | Driver (sync) | Driver (async) | Default port |
| ----- | ------------- | -------------- | ------------ |
| `Mysql` (default) | `pymysql` | — | 3306 |
| `Postgres` | `psycopg2` | `asyncpg` | 5432 |

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

### Tokens

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `TOKEN_MODE` | no | `stateful` | `stateless` \| `hybrid` \| `stateful` — controls Redis usage and JTI revocation |
| `ACCESS_TOKEN_ALGORITHM` | no | `HS256` | Signing algorithm for access tokens (`HS256`, `RS256`, `ES256`) |
| `REFRESH_TOKEN_ALGORITHM` | no | `HS256` | Signing algorithm for refresh tokens |
| `ACCESS_SECRET_KEY` | HS256 only | — | Symmetric signing key for access tokens (omit for RS256/ES256) |
| `REFRESH_SECRET_KEY` | yes | — | Signing key for refresh tokens |
| `ACCESS_PRIVATE_KEY` | RS256/ES256 only | — | PEM private key for signing access tokens (auth service only) |
| `ACCESS_PUBLIC_KEY` | RS256/ES256 only | — | PEM public key distributed to all consumer services |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | no | `120` | Refresh token lifetime |
| `REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS` | no | `3600` | Refresh cookie max-age |
| `TOKENS_ENCRYPTION_KEY` | yes | — | Key for `SessionMiddleware` cookie signing |
| `TOKEN_ISSUER` | no | — | When set, embeds `iss` in tokens and requires a match on validation |
| `TOKEN_AUDIENCE` | no | — | When set, embeds `aud` in tokens and requires a match on validation |
| `ACCESS_KEY_ID` | no | — | Explicit `kid` in JWT headers and JWKS; auto-derived from key fingerprint when unset |
| `JWKS_URI` | no | — | Consumer services: JWKS endpoint URL; enables automatic `JwksKeyResolver` wiring |
| `JWKS_CACHE_TTL_SECONDS` | no | `300` | JWKS key cache TTL in seconds |

**HS256 (default)** — set `ACCESS_SECRET_KEY` and `REFRESH_SECRET_KEY`; leave asymmetric key vars blank.

**RS256 / ES256** — leave `ACCESS_SECRET_KEY` blank; set `ACCESS_TOKEN_ALGORITHM`, `ACCESS_PRIVATE_KEY`, `ACCESS_PUBLIC_KEY`. Generate a key pair:

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

Or use `examples/docker_compose/RS256_m8/keys/generate_keys.sh`.

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
| `FIRST_SUPERUSER` | yes | Email of the bootstrap superuser |
| `FIRST_SUPERUSER_PASSWORD` | yes | Password of the bootstrap superuser |
| `GOOGLE_CLIENT_ID` | no | Google OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | no | Google OAuth2 client secret |
| `PRIVATE_API_SECRET` | yes | Shared secret for `X-Internal-Token` header |

### Observability

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `METRICS_ENABLED` | no | `false` | Expose `GET /metrics` Prometheus endpoint |
| `METRICS_GROUPS` | no | all | Comma-separated metric groups to enable |

### Deployment

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `API_BIND_IP` | `127.0.0.1` | Host IP Traefik binds port 9000 to. Set to `0.0.0.0` for LAN/public exposure |
| `TRUSTED_PROXY_IPS` | `172.16.0.0/12` | CIDR(s) Uvicorn trusts as reverse-proxy source for `X-Forwarded-For` |

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

## Private API

Endpoints under `/user/private/` are for inter-service calls only:

- Must not be exposed to the public internet — enforce at the reverse proxy / Docker network level.
- Every request must include `X-Internal-Token: <PRIVATE_API_SECRET>`.

---

## Consumer Service Integration

`examples/fastapi_service` is a reference implementation showing how a downstream microservice integrates with `auth_user_service` using `auth-sdk-m8`.

### Token validation

```python
from auth_sdk_m8.security import build_access_validator, ValidationHooks

_validator = build_access_validator(settings, hooks=_hooks)
```

`build_access_validator` reads `ACCESS_TOKEN_ALGORITHM`, `ACCESS_SECRET_KEY` / `ACCESS_PUBLIC_KEY`, `TOKEN_ISSUER`, `TOKEN_AUDIENCE`, and `JWKS_URI` directly from a `CommonSettings` instance.

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
# Unit + integration tests
pytest

# Live red-team tests (requires the RS256_m8 stack running)
pytest -m live
```

The `tests/security/` suite covers JWT security, Redis resilience, refresh lifecycle, input sanitisation, JWKS endpoint, OAuth adversarial, iss/aud validation, session-chain invalidation, exception handling, and client IP attribution.

---

## Dependencies

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/) + [Alembic](https://alembic.sqlalchemy.org/)
- [auth-sdk-m8](https://github.com/mano8/auth-sdk-m8) — shared schemas, JWT validation, refresh token rotation, JWKS resolver, base controllers
- [Redis](https://redis.io/) — session revocation, refresh token allowlist, and rate limiting
- [PyJWT](https://pyjwt.readthedocs.io/) + [passlib](https://passlib.readthedocs.io/) + [cryptography](https://cryptography.io/)
- [google-auth](https://google-auth.readthedocs.io/) — Google OAuth2

---

## License

MIT © Eli Serra
