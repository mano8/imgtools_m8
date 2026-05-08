# local_mysql_m8

Production-adjacent local stack using **MariaDB 12.2** (pinned version) as the primary database.
All infrastructure ports are bound to `127.0.0.1` only — nothing is exposed to the network.
Includes `acme.json` for Traefik TLS certificate management (HTTPS out of the box).

## Services

| Service | Image | Port(s) |
|---|---|---|
| Traefik | traefik:v3.3 | `8000` (HTTP), `4430` (HTTPS), `9000` (services), `127.0.0.1:8080` (dashboard) |
| MariaDB | bitnami/mariadb:12.2 | `127.0.0.1:3306` |
| Redis | redis:7.4-alpine | `127.0.0.1:6379` |
| auth_user_service | local build | via Traefik `/user` |
| fastapi_service | local build | via Traefik `/fastapi` |

## Token mode (`TOKEN_MODE`)

Set in `auth.env`. Default in this stack's env file: **`hybrid`**.

| Value | Access token | Refresh token | Redis usage | DB session |
|---|---|---|---|---|
| `stateless` | self-validating JWT | self-validating JWT | not used | not created |
| `hybrid` | self-validating JWT | Redis allowlist (`rt:<jti>`) | refresh JTI allowlist | created |
| `stateful` | Redis blacklist on every request | Redis allowlist (`rt:<jti>`) | blacklist + allowlist | created + deleted on logout |

`hybrid` is the recommended default here: access tokens are verified locally (no Redis round-trip on every request), while refresh token reuse is detected immediately via the Redis allowlist.

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

### Google OAuth

Required by `auth_user_service` settings validation even when OAuth login is not used.
Set placeholder values to disable:
```
GOOGLE_CLIENT_ID="changethis"
GOOGLE_CLIENT_SECRET="changethis"
```

## Quick start

```sh
cp example.env.txt .env             # edit secrets
touch traefik/acme.json && chmod 600 traefik/acme.json   # required by Traefik ACME
docker compose up --build
```

The auth API is available at `https://localhost:4430/user/docs`.

## Volumes

| Path | Purpose |
|---|---|
| `../../../auth_user_service` | Live source mount |
| `./mysql_db` | Persistent MariaDB data |
| `./redis/redis_data` | Persistent Redis snapshots |
| `./shared_migrations` | Alembic migration files shared between services |
| `./traefik/acme.json` | TLS certificates managed by Traefik ACME |
