# stateful_m8

Full **stateful** stack with **MariaDB**, **Redis**, and a **Prometheus + Grafana** observability layer.
Designed for validating the complete stateful auth flow — every login/logout writes to both Redis and the DB session table, and those writes are visible in Grafana dashboards.

## Services

| Service | Image | Port(s) |
|---|---|---|
| Traefik | traefik:v3.3 | `8000` (HTTP), `4430` (HTTPS), `9000` (services), `8080` (dashboard) |
| MariaDB | bitnami/mariadb:latest | `3306` |
| Redis | redis:7.4-alpine | `6379` |
| Prometheus | ubuntu/prometheus:3.11-24.04_stable | `127.0.0.1:9090` |
| Grafana | grafana/grafana:main-ubuntu | `127.0.0.1:3000` |
| auth_user_service | local build | via Traefik `/user` |
| fastapi_service | local build | via Traefik `/fastapi` |

## Token mode (`TOKEN_MODE`)

Set in `auth.env` (and `.env` for the compose `environment` substitution).
Default in this stack: **`stateful`**.

| Value | Access token | Refresh token | Redis keys written | DB session |
|---|---|---|---|---|
| `stateless` | self-validating JWT | self-validating JWT | none | none |
| `hybrid` | self-validating JWT | Redis allowlist (`rt:<jti>`) | `rt:<jti>` | created |
| `stateful` | Redis blacklist on every request | Redis allowlist (`rt:<jti>`) | `rt:<jti>` + `jwt:blacklist:<jti>` on logout | created + deleted on logout |

In `stateful` mode:

- **Login** → writes `rt:<jti>` to Redis (refresh allowlist) and creates a `client_session` DB row.
- **Token refresh** → atomically rotates `rt:<old_jti>` → `rt:<new_jti>` in Redis and updates the DB row.
- **Logout** → deletes `rt:<jti>` from Redis, writes `jwt:blacklist:<jti>` with a TTL matching the access token's remaining lifetime, and deletes the DB session row.
- **Request validation** → checks `jwt:blacklist:<jti>` on every authenticated request.

After a full login → logout cycle Redis returns to an empty keyspace (the blacklist key expires automatically via its TTL).

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

## Observability

Grafana is pre-provisioned at `http://localhost:3000`.
The Redis datasource plugin tracks keyspace activity — use `INFO keyspace` in `redis-cli` or the Grafana Redis panel to confirm writes after login.

Prometheus scrapes metrics at `http://localhost:9090`.
Grafana config lives in `./grafana/provisioning/`.

## Quick start

```sh
cp example.env.txt .env             # edit secrets and verify TOKEN_MODE=stateful
docker compose up --build
```

The auth API is available at `https://localhost:4430/user/docs`.

Verify Redis writes after a login:
```sh
docker compose exec redis_cache redis-cli -a "$REDIS_PASSWORD" INFO keyspace
# Expected: db0:keys=1,expires=1,...
```

## Volumes

| Path | Purpose |
|---|---|
| `../../../auth_user_service` | Live source mount |
| `./mysql_db` | Persistent MariaDB data |
| `./redis/redis_data` | Persistent Redis snapshots |
| `./prometheus/data` | Prometheus TSDB |
| `./grafana/data` | Grafana dashboards and state |
| `./shared_migrations` | Alembic migration files shared between services |
