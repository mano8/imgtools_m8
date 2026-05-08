# dev_postgres_m8

Local development stack using **PostgreSQL** as the primary database.
All service ports are exposed on all interfaces for easy tool access (DB clients, Redis GUIs).
Source code directories are bind-mounted so changes reload without rebuilding.

## Services

| Service | Image | Port(s) |
|---|---|---|
| Traefik | traefik:v3.3 | `8000` (HTTP), `4430` (HTTPS), `9000` (services), `8080` (dashboard) |
| PostgreSQL | postgres:16-alpine | `${DB_PORT}` |
| Redis | redis:7.4-alpine | `6379` |
| auth_user_service | local build | via Traefik `/user` |
| fastapi_service | local build | via Traefik `/fastapi` |

## Token mode (`TOKEN_MODE`)

Set in `auth.env` (and propagated via the compose `environment` block).
Default when unset: **`stateful`**.

| Value | Access token | Refresh token | Redis usage | DB session |
|---|---|---|---|---|
| `stateless` | self-validating JWT | self-validating JWT | not used | not created |
| `hybrid` | self-validating JWT | Redis allowlist (`rt:<jti>`) | refresh JTI allowlist | created |
| `stateful` | Redis blacklist on every request | Redis allowlist (`rt:<jti>`) | blacklist + allowlist | created + deleted on logout |

### Key env vars for token signing

```
# HS256 (default) — symmetric secret
ACCESS_SECRET_KEY="..."
REFRESH_SECRET_KEY="..."
ACCESS_TOKEN_ALGORITHM="HS256"
REFRESH_TOKEN_ALGORITHM="HS256"

# RS256 / ES256 — asymmetric keys
# Comment out ACCESS_SECRET_KEY, then:
ACCESS_TOKEN_ALGORITHM="RS256"
ACCESS_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n..."   # auth service only
ACCESS_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n..."         # all consumer services
```

Generate a key pair:
```sh
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

## Quick start

```sh
cp auth.env.example auth.env        # edit secrets
cp api.env.example api.env          # edit secrets
docker compose up --build
```

The auth API is available at `https://localhost:4430/user/docs` (self-signed cert — accept the browser warning in local dev).

## Volumes

| Path | Purpose |
|---|---|
| `../../../auth_user_service` | Live source mount — no rebuild needed for Python changes |
| `./postgres_data` | Persistent DB data |
| `./redis/redis_data` | Persistent Redis snapshots (`save 20 1`) |
| `./shared_migrations` | Alembic migration files shared between services |
