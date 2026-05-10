# fa-auth-m8

A self-contained FastAPI authentication microservice designed to run as a Docker container via Docker Compose. It provides JWT-based authentication, Google OAuth2, session management, user management, and private inter-service endpoints for any project in the m8 stack.

---

## Features

- Email/password login with bcrypt password hashing
- Google OAuth2 login
- JWT access + refresh token pair (refresh token delivered via HttpOnly cookie, rotated on every use)
- Session tracking and revocation via Redis
- Login rate limiting per email (Redis-backed)
- Role-based access control (`user`, `admin`, `superuser`)
- User management CRUD (superuser only)
- Dashboard activity endpoints
- Private inter-service API (protected by shared secret + Docker network isolation)
- MySQL **or** PostgreSQL — switchable via a single env var
- Alembic migrations (auto-generated on first start)
- VS Code remote debugger support

---

## Architecture

```
┌─────────────────────────────────────────┐
│            Docker Compose               │
│                                         │
│  ┌──────────────┐   ┌────────────────┐  │
│  │  auth-service│   │  MySQL/Postgres │  │
│  │  :8000       │──▶│  :3306 / :5432 │  │
│  └──────┬───────┘   └────────────────┘  │
│         │           ┌────────────────┐  │
│         └──────────▶│  Redis :6379   │  │
│                     └────────────────┘  │
└─────────────────────────────────────────┘
```

Other services on the same Docker network can call the private API at `http://auth-service:8000/user/private/`.

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
| oauth-login | * | `/oauth/...` | OAuth2 password-flow endpoints |
| google-auth | GET | `/google/login` | Initiate Google OAuth2 flow |
| google-auth | GET | `/google/callback` | Google OAuth2 callback |
| profile | GET/PATCH | `/profile/me` | Read/update own profile |
| profile | POST | `/profile/me/avatar` | Upload profile avatar |
| sessions | GET/DELETE | `/sessions/...` | List and revoke own sessions |
| users | GET/POST/PATCH/DELETE | `/users/...` | User management (superuser only) |
| dashboard | GET | `/dashboard/users/activity/` | User activity stats (superuser only) |
| private | * | `/private/...` | Inter-service endpoints — Docker network + `X-Internal-Token` header |

Interactive docs are available at `{BACKEND_HOST}{API_PREFIX}/docs` when `SET_DOCS=true`.

---

## Quick Start

### 1. Copy and configure the environment file

```bash
cp auth_user_service/.env.example auth_user_service/.env
```

Edit `.env` and fill in all required values (see [Environment Variables](#environment-variables)).

### 2. Start the stack

```bash
docker compose up --build
```

Alembic migrations run automatically on startup. The first run also seeds the superuser defined by `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`.

### 3. Verify

```
GET http://localhost:8000/user/docs
```

---

## Choosing a Database

Set `SELECTED_DB` in `.env`:

| Value | Driver (sync) | Driver (async) | Default port |
| ----- | ------------- | -------------- | ------------ |
| `Mysql` (default) | `pymysql` | — | 3306 |
| `Postgres` | `psycopg2` | `asyncpg` | 5432 |

Update `DB_HOST`, `DB_PORT`, and `DB_DATABASE` accordingly. Both drivers ship in the container image.

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
| `ACCESS_PRIVATE_KEY` | RS256/ES256 only | — | PEM private key used by the auth service to sign access tokens |
| `ACCESS_PUBLIC_KEY` | RS256/ES256 only | — | PEM public key distributed to all consuming services for verification |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | no | `120` | Refresh token lifetime |
| `REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS` | no | `3600` | Refresh cookie max-age |
| `TOKENS_ENCRYPTION_KEY` | yes | — | Token payload encryption key |
| `TOKEN_ISSUER` | no | — | When set, embeds `iss` in issued tokens and requires a match on validation |
| `TOKEN_AUDIENCE` | no | — | When set, embeds `aud` in issued tokens and requires a match on validation |
| `ACCESS_KEY_ID` | no | — | Explicit `kid` embedded in JWT headers and JWKS; auto-derived from key fingerprint when unset |

**HS256 (default)** — set `ACCESS_SECRET_KEY` and `REFRESH_SECRET_KEY`; leave `ACCESS_PRIVATE_KEY` / `ACCESS_PUBLIC_KEY` blank.

**RS256 / ES256** — leave `ACCESS_SECRET_KEY` blank; set `ACCESS_TOKEN_ALGORITHM`, `ACCESS_PRIVATE_KEY`, and `ACCESS_PUBLIC_KEY`.  Generate a key pair with:

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

### Database

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `SELECTED_DB` | no | `Mysql` | `Mysql` or `Postgres` |
| `DB_HOST` | yes | — | Database host |
| `DB_PORT` | yes | — | Database port |
| `DB_DATABASE` | yes | — | Database name |
| `DB_USER` | yes | — | Database user |
| `DB_PASSWORD` | yes | — | Database password (strong password required) |
| `DB_ENGINE` | no | `InnoDB` | MySQL storage engine (ignored for Postgres) |
| `DB_CHARSET` | no | `utf8mb4` | MySQL charset (ignored for Postgres) |

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
| `GOOGLE_CLIENT_ID` | no | Google OAuth2 client ID (required only if using Google login) |
| `GOOGLE_CLIENT_SECRET` | no | Google OAuth2 client secret (required only if using Google login) |
| `PRIVATE_API_SECRET` | yes | Shared secret for private inter-service endpoints (`X-Internal-Token` header) |

### Static / Templates

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `STATIC_BASE_PATH` | yes | Absolute path to static files directory |
| `TEMPLATES_BASE_PATH` | yes | Absolute path to Jinja2 templates directory |

---

## Infrastructure Resilience

The service is designed to degrade gracefully when Redis or the database is temporarily unavailable rather than crashing with opaque 500 errors.

### Redis unavailable

| `TOKEN_MODE` | Login | Refresh | Logout | Google OAuth |
| ------------ | ----- | ------- | ------ | ------------ |
| `stateless` | ✅ unaffected | ✅ unaffected | ✅ unaffected | ❌ 503 (PKCE requires Redis) |
| `hybrid` | ✅ works, rate limiting skipped | ✅ works, JTI check skipped | ✅ works | ❌ 503 |
| `stateful` | ✅ works, rate limiting skipped | ✅ works, JTI allowlist check skipped | ✅ works | ❌ 503 |

> In `stateful`/`hybrid` mode with Redis down, login still succeeds but token revocation is unavailable.  The `/health/` endpoint reflects this with `effective_mode: stateless_degraded`.  A `CRITICAL` log line is emitted at startup when this condition is detected.

### Database unavailable

All routes that touch the database return `503 Service Unavailable` with a clear message.  A `CRITICAL` log line is emitted at startup.

### Health endpoint

```http
GET {API_PREFIX}/health/
```

Example response when fully operational:

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

Example response with Redis down in stateful mode:

```json
{
  "status": "degraded",
  "token_mode": "stateful",
  "effective_mode": "stateless_degraded",
  "redis": "unavailable",
  "database": "ok",
  "revocation_available": false,
  "rate_limiting_available": false,
  "degraded_since": "2026-05-10T12:34:56.789123+00:00"
}
```

`degraded_since` is the UTC timestamp when Redis first became unreachable in the current process lifetime, or `null` when Redis is healthy.  Use it in alerting to detect silent degradation that persists beyond an acceptable window.

### Deployment modes

The stack supports three security postures depending on the target environment.  Configure the appropriate one before going live.

| Mode | `API_BIND_IP` | TLS | HSTS | Secure cookies | Use when |
| ---- | ------------- | --- | ---- | -------------- | -------- |
| **Development** | `0.0.0.0` *(or omit)* | self-signed OK | off | off (`ENVIRONMENT=local`) | local machine only, Docker dev loop |
| **Private LAN / homelab** | `0.0.0.0` or `127.0.0.1` | self-signed / local CA recommended | off | on | Raspberry Pi, NAS, private LAN, edge devices |
| **Public / production** | `127.0.0.1` | valid cert required | on (opt-in, see below) | on | VPS, cloud, any internet-facing host |

> Self-signed certificates with a local CA (e.g. [mkcert](https://github.com/FiloSottile/mkcert)) are a good fit for private LAN deployments.  Modern LANs are not uniformly trusted — IoT devices, guest Wi-Fi, and ARP spoofing are real risks even on a home network.

### Running behind a reverse proxy (real client IP)

Audit logs, rate-limit keys, and reuse-detection events all record the client IP.  When the service runs behind Traefik (or any reverse proxy) this requires a coordinated three-layer setup — failing to configure any one layer either breaks IP attribution or opens a spoofing path.

**1. Traefik** — add `forwardedHeaders.trustedIPs` to each entrypoint in `traefik.yml`:

```yaml
entryPoints:
  api:
    address: ":9000"
    forwardedHeaders:
      trustedIPs:
        - "127.0.0.1/32"
        - "172.16.0.0/12"   # Docker bridge networks
        - "::1/128"
```

This instructs Traefik to strip any `X-Forwarded-For` sent by a client and replace it with the real peer address.  Without this, clients can forge their IP.

**2. Uvicorn** — the startup script (`docker_start.sh`) reads `TRUSTED_PROXY_IPS` (defaults to `172.16.0.0/12`) and passes it to uvicorn:

```text
--proxy-headers --forwarded-allow-ips=<TRUSTED_PROXY_IPS>
```

Set `TRUSTED_PROXY_IPS` in the container environment to match your actual Docker network CIDR.  Never use `*` — that would let any client spoof their IP.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `API_BIND_IP` | `127.0.0.1` | Host IP Traefik binds port 9000 to. Set to `0.0.0.0` for LAN/public exposure |
| `TRUSTED_PROXY_IPS` | `172.16.0.0/12` | CIDR(s) uvicorn trusts as a reverse proxy source for `X-Forwarded-For` |

**3. Application** — `_client_ip()` reads the leftmost IP from `X-Forwarded-For`, which is the real client address only because the proxy chain above has been sanitized.  Without layers 1 and 2 this value is untrustworthy.

### HSTS (opt-in, public deployments only)

`Strict-Transport-Security` is **not enabled by default** because in self-hosted and LAN environments it can cause serious breakage: once a browser receives the header it will refuse all HTTP connections to that hostname for the configured period — even if you later disable HSTS or rotate to a new certificate.

To enable HSTS, uncomment the relevant block in `traefik/dynamic_conf.yml`:

```yaml
# stsSeconds: 31536000       # 1 year
# stsIncludeSubdomains: true
# stsPreload: false
```

Only do this when:

- TLS is correctly configured with a stable, trusted certificate
- The hostname will remain HTTPS-only for the full `stsSeconds` period
- You understand that `stsPreload: true` permanently adds the domain to browser preload lists

---

## Private API

Endpoints under `/user/private/` are intended for inter-service calls only:

- They **must not** be exposed to the public internet — enforce this at the reverse proxy / Docker network level.
- Every request must include the header `X-Internal-Token: <PRIVATE_API_SECRET>`.

---

## Consumer Service Integration

`examples/fastapi_service` is a reference implementation showing how a downstream microservice integrates with `auth_user_service` using `auth-sdk-m8`.

### Token validation

```python
from auth_sdk_m8.security import build_access_validator, ValidationHooks

_validator = build_access_validator(settings, hooks=_hooks)
```

`build_access_validator` reads `ACCESS_TOKEN_ALGORITHM`, `ACCESS_SECRET_KEY` / `ACCESS_PUBLIC_KEY`, `TOKEN_ISSUER`, `TOKEN_AUDIENCE`, and `JWKS_URI` directly from a `CommonSettings` instance.  No boilerplate needed.

### JWKS-based key validation (RS256/ES256)

When `JWKS_URI` is set in the consumer's settings, `build_access_validator` automatically wires up `JwksKeyResolver` instead of a static public key.  The resolver fetches `/.well-known/jwks.json` from the auth service, caches keys by `kid`, and refreshes on cache miss — supporting zero-downtime key rotation.

```ini
# consumer .env
ACCESS_TOKEN_ALGORITHM=RS256
JWKS_URI=http://auth-service/user/.well-known/jwks.json
JWKS_CACHE_TTL_SECONDS=300   # optional, default 300
```

The auth service serves the JWKS endpoint at `{API_PREFIX}/.well-known/jwks.json`.  HS256 configurations return `{"keys": []}` — the shared secret is never published.

### Revocation check (stateful mode)

Consumer services must share the same Redis instance as `auth_user_service` and set `TOKEN_MODE="stateful"`.  The `AccessTokenBlacklist` class checks whether a JTI has been blacklisted by the auth service:

```python
from auth_sdk_m8.security import AccessTokenBlacklist

if settings.TOKEN_MODE == "stateful" and redis is not None:
    if AccessTokenBlacklist(redis).is_revoked(payload.jti):
        raise HTTPException(status_code=403, detail="Token has been revoked.")
```

### Issuer / audience enforcement (opt-in)

Set `TOKEN_ISSUER` and `TOKEN_AUDIENCE` to the **same values** in both `auth_user_service` and every consumer service.  When set, the auth service embeds `iss`/`aud` claims in issued tokens and all validators require an exact match — preventing token reuse across services or issuers.  Leaving them unset (default) skips enforcement for backward compatibility.

---

## Development

### Run locally (without Docker)

```bash
cd auth_user_service
pip install -r requirements-fastapi.txt
uvicorn auth_user_service.main:app --host 0.0.0.0 --port 8000 --reload
```

### VS Code remote debugging

Set `VSCODE_DEBUG=true` in the container environment. The startup script will launch `debugpy` on port `5678` and wait for the debugger to attach before starting Uvicorn.

### Database migrations

Migrations are generated and applied automatically on container start. To run them manually:

```bash
# Inside the container or with the project on PYTHONPATH
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
pytest
```

---

## Dependencies

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/) + [Alembic](https://alembic.sqlalchemy.org/)
- [auth-sdk-m8](https://github.com/mano8/auth-sdk-m8) — shared schemas, JWT validation, refresh token rotation, base controllers
- [Redis](https://redis.io/) — session revocation and rate limiting
- [PyJWT](https://pyjwt.readthedocs.io/) + [passlib](https://passlib.readthedocs.io/) + [cryptography](https://cryptography.io/)
- [google-auth](https://google-auth.readthedocs.io/) — Google OAuth2

---

## License

MIT © Eli Serra
