# stateful_m8

**MariaDB 12** + **HS256** symmetric tokens + **stateful** token mode + **Prometheus & Grafana** observability. Designed for validating the complete stateful auth flow and exploring metrics.

**Choose this when:** you want to watch what happens in Redis and the database during login/logout cycles, or need to develop against a metrics dashboard.

---

## Summary

- [Architecture](#architecture)
- [Services](#services)
- [Setup](#setup)
- [Token mode: stateful](#token-mode-stateful)
- [Observability](#observability)
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
       ├──► /user/*      → auth_user_service :8000
       └──► /fastapi/*   → fastapi_service :8000
                │
       ┌────────┴────────┐
       ▼                 ▼
  m8_db (MariaDB 12)  redis_cache (Redis 7.4)
                         │
                   (access token blacklist
                    + refresh token store)

  Prometheus :9090  ←── scrapes /user/metrics
       │
  Grafana :3000
```

---

## Services

| Service | Image | Accessible at |
| --- | --- | --- |
| traefik | traefik:v3.3 | `:8000` (HTTP), `:4430` (HTTPS), `:9000` (API), `:8080` (dashboard) |
| m8_db | mariadb:12-ubi | `127.0.0.1:3306` |
| redis_cache | redis:7.4-alpine | `127.0.0.1:6379` |
| prometheus | ubuntu/prometheus:3.11-24.04_stable | `127.0.0.1:9090` |
| grafana | grafana/grafana:13.1.0-25530058790 | `127.0.0.1:3000` |
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

### 3. Start

```sh
docker compose up --build
```

Migrations run automatically on first boot. The superuser defined in `.env` is created
if it does not exist.

---

## Token mode: stateful

This stack defaults to `TOKEN_MODE=stateful`:

| Mode | Access token validated by | Refresh token | Redis round-trip per request |
| --- | --- | --- | --- |
| `stateless` | JWT signature only | JWT signature only | No |
| `hybrid` | JWT signature only | Redis allowlist | No |
| **`stateful`** | **JWT signature + Redis blacklist** | **Redis allowlist** | **Yes** |

What happens in Redis and the database during a full session:

- **Login** → writes `rt:<jti>` to Redis (refresh allowlist) and creates a `client_session`
  DB row.
- **Token refresh** → atomically rotates `rt:<old_jti>` → `rt:<new_jti>` in Redis and
  updates the DB row. Reuse of an old refresh token is detected immediately.
- **Logout** → deletes `rt:<jti>`, writes `jwt:blacklist:<jti>` with a TTL matching the
  access token's remaining lifetime, and removes the DB session row.
- **Request validation** → checks `jwt:blacklist:<jti>` on every authenticated request.

After a full login → logout cycle, the blacklist key expires automatically via its TTL
and Redis returns to an empty keyspace.

Verify writes after a login:

```sh
docker compose exec redis_cache redis-cli -a "$REDIS_PASSWORD" INFO keyspace
# Expected: db0:keys=1,expires=1,...
```

---

## Observability

### Grafana — `http://localhost:3000`

Pre-provisioned with a Prometheus datasource. Default credentials: `admin` / `admin`
(change on first login).

Dashboard config lives in `./grafana/provisioning/`. Add your own dashboards by dropping
JSON files into the `dashboards/` subdirectory.

### Prometheus — `http://localhost:9090`

Scrapes metrics from `auth_user_service` at `/user/metrics` (enabled by `METRICS_ENABLED=true`
in `auth.env`). Use the Prometheus expression browser to query request counts, latency
histograms, and Redis operation rates.

Useful queries to start with:

```promql
# HTTP request rate by endpoint
rate(http_requests_total[1m])

# 95th percentile response time
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

---

## URLs

| What | URL |
| --- | --- |
| Auth API | `http://localhost:9000/user/` |
| Auth interactive docs | `http://localhost:9000/user/docs` |
| Auth ReDoc | `http://localhost:9000/user/redoc` |
| FastAPI service docs | `http://localhost:9000/fastapi/docs` |
| Traefik dashboard | `http://localhost:8080` |
| Prometheus | `http://localhost:9090` |
| Grafana | `http://localhost:3000` |
| HTTPS | `https://localhost:4430/user/docs` (self-signed cert — accept browser warning) |

---

## Port map

| Port | Bound to | Purpose |
| --- | --- | --- |
| `8000` | `0.0.0.0` | Traefik HTTP |
| `4430` | `0.0.0.0` | Traefik HTTPS |
| `9000` | `127.0.0.1` | API services entry (set `API_BIND_IP` in `.env` to expose on LAN) |
| `8080` | `127.0.0.1` | Traefik dashboard |
| `3306` | `127.0.0.1` | MariaDB |
| `6379` | `127.0.0.1` | Redis |
| `9090` | `127.0.0.1` | Prometheus |
| `3000` | `127.0.0.1` | Grafana |

---

## Configuration reference

### `.env` — shared across all services

| Variable | Default | Notes |
| --- | --- | --- |
| `TOKEN_MODE` | `stateful` | `stateless` / `hybrid` / `stateful` |
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
| `METRICS_ENABLED` | `true` — exposes `/user/metrics` for Prometheus to scrape |
| `AUTH_SERVICE_ROLE` | `issuer` — this service signs tokens |

### `api.env` — consumer service only

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` — verifies tokens, does not sign them |
| `METRICS_ENABLED` | `true` — exposes `/fastapi/metrics` |

---

## Volumes

| Path | Purpose |
| --- | --- |
| `./db_data` | Persistent MariaDB data |
| `./redis/redis_data` | Persistent Redis snapshots |
| `./prometheus/data` | Prometheus TSDB |
| `./grafana/data` | Grafana dashboards and state |
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

# Inspect Redis keyspace after a login
docker compose exec redis_cache redis-cli -a "$REDIS_PASSWORD" INFO keyspace

# Stop (keeps volumes and data)
docker compose stop

# Stop and remove containers (keeps data volumes)
docker compose down

# Full reset — stops containers and wipes the database (prompts for confirmation)
# Note: Prometheus and Grafana data in ./prometheus/data and ./grafana/data persist.
# Delete those directories manually if you also want to reset observability state.
bash init.sh --reset-db
```

---

## Troubleshooting

**Services fail to start immediately** — `auth_user_service` waits for MariaDB to pass
its health check. MariaDB can take 20–30 s on first boot.

**`changethis` rejection on startup** — replace all `changethis` values in `.env`
and `auth.env`.

**Grafana shows no data** — confirm `METRICS_ENABLED=true` in `auth.env`, then make
at least one request to generate metrics. Check Prometheus targets at
`http://localhost:9090/targets` to confirm the auth service is being scraped.

**Port conflict** — if `3306`, `6379`, `9090`, or `3000` are already in use, identify
the process and stop it, or comment out the conflicting `ports:` entry in
`docker-compose.yml` if you don't need direct host access to that service.

---

## Live testing

Run the live test suite against this stack (requires the stack to be up):

```sh
# From the repo root
pytest -m live_hs256 --no-cov      # HS256-specific attacks
pytest -m live_stateful --no-cov   # Token revocation guarantees
pytest -m live_security --no-cov   # Universal attack categories (A–M)
```

Manual smoke test:

```sh
curl http://localhost:9000/user/health/
# Expected: {"status":"ok","token_mode":"stateful","redis":"ok","database":"ok",...}
```

After at least one request, check Prometheus has data:

```sh
curl http://localhost:9090/api/v1/query?query=up
```

---

> [Docker Compose examples](../README.md) · [Repository root](https://github.com/mano8/fa-auth-m8/tree/main)
