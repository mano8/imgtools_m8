# hardened_m8

**PostgreSQL 16** + **RS256 asymmetric token signing** + **stateful** token mode + **Prometheus & Grafana** observability + **container hardening** + **network segmentation**.

`auth_user_service` runs from the published Docker Hub image (`tepochtli/fa-auth-m8:latest`). Secrets live in env files — no Vault required.

**Choose this when:** you want production-grade container posture (read-only rootfs, dropped capabilities, resource limits) and observability, but don't need HashiCorp Vault. Use [vault_m8](../vault_m8/) when you also need secrets-manager injection.

---

## Summary

- [Architecture](#architecture)
- [Hardening baseline](#hardening-baseline)
- [Services](#services)
- [Setup](#setup)
- [Token mode: stateful](#token-mode-stateful)
- [Observability](#observability)
- [URLs](#urls)
- [Port map](#port-map)
- [Configuration reference](#configuration-reference)
- [Key rotation](#key-rotation)
- [Volumes](#volumes)
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
       │ (app_net)
       ├──► /user/*      → auth_user_service :8000  (RS256 issuer)
       └──► /fastapi/*   → fastapi_service :8000    (RS256 consumer via JWKS)

  app_net ─── Traefik + auth + fastapi + Prometheus + Grafana
  data_net ── m8_db (PostgreSQL 16) + redis_cache (Redis 7.4)  [internal: true]

  Auth and fastapi services sit on both networks.
  Traefik sits on app_net only — cannot reach DB or Redis directly.
```

### Network segmentation

Two Docker networks isolate external-facing traffic from the data tier:

| Network | Services | internet gateway |
| --- | --- | --- |
| `app_net` | traefik, auth, fastapi, prometheus, grafana | yes |
| `data_net` | m8_db, redis_cache, auth, fastapi | **no** (`internal: true`) |

`data_net` has no gateway — containers on it cannot initiate outbound internet connections, and Traefik (on `app_net` only) cannot reach the database or Redis directly.

---

## Hardening baseline

Applied to `auth_user_service` and `fastapi_service`:

| Option | Value | Effect |
| --- | --- | --- |
| `security_opt` | `no-new-privileges:true` | Blocks privilege escalation via setuid/setgid |
| `cap_drop` | `ALL` | Removes all Linux capabilities |
| `read_only` | `true` | Root filesystem is read-only |
| `tmpfs` | `/tmp`, `/run` | Writable in-memory mounts for temp files |
| `PYTHONDONTWRITEBYTECODE` | `1` | Prevents Python writing `.pyc` to read-only paths |
| `deploy.resources.limits` | `1 CPU`, `512 MB` | Prevents resource exhaustion |

Auth degradation settings in `auth.env`:

| Setting | Value | Effect |
| --- | --- | --- |
| `AUTH_STRICT_MODE` | `true` | Overrides all per-control modes to `fail_closed` |
| `RATE_LIMIT_FAILURE_MODE` | `fail_closed` | Redis outage → 503, not open |
| `ACCESS_REVOCATION_FAILURE_MODE` | `fail_closed` | Redis outage → tokens not accepted |

---

## Services

| Service | Image | Accessible at |
| --- | --- | --- |
| traefik | traefik:v3.3 | `:8000` (HTTP), `:4430` (HTTPS), `:9000` (API), `:8080` (dashboard) |
| m8_db | postgres:16-alpine | `127.0.0.1:5432` |
| redis_cache | redis:7.4-alpine | `127.0.0.1:6379` |
| prometheus | ubuntu/prometheus:3.11-24.04_stable | `127.0.0.1:9090` |
| grafana | grafana/grafana:13.1.0 | `127.0.0.1:3000` |
| auth_user_service | [tepochtli/fa-auth-m8:latest](https://hub.docker.com/r/tepochtli/fa-auth-m8) | via Traefik at `/user` |
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
DB_PASSWORD=<strong-postgres-root-password>
AUTH_DB_PASSWORD=<strong-auth-db-password>
API_DB_PASSWORD=<strong-api-db-password>
REDIS_PASSWORD=<strong-redis-password>
```

Open `auth.env` and replace every `changethis`:

```ini
DB_USER=<same-as-AUTH_DB_USER-in-.env>
DB_PASSWORD=<same-as-AUTH_DB_PASSWORD-in-.env>
REDIS_PASSWORD=<same-as-REDIS_PASSWORD-in-.env>
REFRESH_SECRET_KEY=<64-char-random>
PRIVATE_API_SECRET=<64-char-random>
TOKENS_ENCRYPTION_KEY=<64-char-random>
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=<strong-password>
```

Open `api.env` and replace every `changethis`:

```ini
DB_USER=<same-as-API_DB_USER-in-.env>
DB_PASSWORD=<same-as-API_DB_PASSWORD-in-.env>
REDIS_PASSWORD=<same-as-REDIS_PASSWORD-in-.env>
REFRESH_SECRET_KEY=<64-char-random>
```

`ACCESS_KEY_ID` in `auth.env` can stay as `changethis_hex_kid` — `init.sh` derives and writes the correct fingerprint automatically.

### 2. Generate RSA key pair + TLS certificates

```sh
bash init.sh
```

> **Windows:** use **Git Bash** or **WSL**.

### 3. Start

```sh
docker compose up -d
```

`auth_user_service` pulls from Docker Hub — no `--build` needed for it. Only `fastapi_service` is built locally.

> **Pin for production:** replace `tepochtli/fa-auth-m8:latest` with a specific release tag
> (e.g. `tepochtli/fa-auth-m8:0.9.0`) in `docker-compose.yml` to ensure reproducible deployments.

---

## Token mode: stateful

| Mode | Access token validated by | Refresh token | Redis round-trip per request |
| --- | --- | --- | --- |
| `stateless` | JWT signature only | JWT signature only | No |
| `hybrid` | JWT signature only | Redis allowlist | No |
| **`stateful`** | **JWT signature + Redis blacklist** | **Redis allowlist** | **Yes** |

With `AUTH_STRICT_MODE=true` and `ACCESS_REVOCATION_FAILURE_MODE=fail_closed`, a Redis outage causes authenticated requests to return **503** rather than bypassing revocation checks. This is the deliberately conservative posture for this stack.

---

## Observability

### Grafana — `http://localhost:3000`

Pre-provisioned with a Prometheus datasource. Default credentials: `admin` / `foobar`
(change on first login via `grafana/config.monitoring`).

### Prometheus — `http://localhost:9090`

Scrapes `auth_user_service` at `/user/metrics` and `fastapi_service` at `/fastapi/metrics`.
Alert rules in `prometheus/alerts.yml` cover API key rate-limit ratios and flush latency.

---

## URLs

| What | URL |
| --- | --- |
| Auth API | `http://localhost:9000/user/` |
| Auth interactive docs | `http://localhost:9000/user/docs` |
| JWKS endpoint | `http://localhost:9000/user/.well-known/jwks.json` |
| FastAPI service docs | `http://localhost:9000/fastapi/docs` |
| Health check | `http://localhost:9000/user/health/` |
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
| `5432` | `127.0.0.1` | PostgreSQL |
| `6379` | `127.0.0.1` | Redis |
| `9090` | `127.0.0.1` | Prometheus |
| `3000` | `127.0.0.1` | Grafana |

---

## Configuration reference

### `.env` — shared infrastructure

| Variable | Default | Notes |
| --- | --- | --- |
| `API_BIND_IP` | `127.0.0.1` | Set to `0.0.0.0` to expose port 9000 on LAN |
| `DB_USER` | `m8_admin` | PostgreSQL superuser for bootstrap only |
| `DB_PASSWORD` | — | PostgreSQL superuser password |
| `DB_PORT` | `5432` | PostgreSQL port |
| `AUTH_DB_USER` / `AUTH_DB_PASSWORD` / `AUTH_DB_NAME` | — | Per-service isolation (Scenario 2) |
| `API_DB_USER` / `API_DB_PASSWORD` / `API_DB_NAME` | — | Per-service isolation (Scenario 2) |
| `REDIS_PASSWORD` | — | Redis password |

### `auth.env` — auth service (issuer)

| Variable | Default | Notes |
| --- | --- | --- |
| `ACCESS_TOKEN_ALGORITHM` | `RS256` | Asymmetric signing |
| `REFRESH_TOKEN_ALGORITHM` | `HS256` | Refresh tokens remain symmetric |
| `ACCESS_PRIVATE_KEY_FILE` | `/opt/keys/private.pem` | Path inside the container |
| `ACCESS_PUBLIC_KEY_FILE` | `/opt/keys/public.pem` | Path inside the container |
| `ACCESS_KEY_ID` | — | Stable `kid` written by `init.sh` |
| `TOKEN_MODE` | `stateful` | `stateless` / `hybrid` / `stateful` |
| `AUTH_STRICT_MODE` | `true` | Overrides all failure modes to `fail_closed` |
| `RATE_LIMIT_FAILURE_MODE` | `fail_closed` | Redis outage → 503 on rate-limited endpoints |
| `ACCESS_REVOCATION_FAILURE_MODE` | `fail_closed` | Redis outage → tokens not accepted |
| `METRICS_ENABLED` | `true` | Exposes `/user/metrics` for Prometheus |

### `api.env` — consumer service

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` — verifies tokens via JWKS, does not sign them |
| `JWKS_URI` | `http://auth_user_service:8000/user/.well-known/jwks.json` |
| `JWKS_CACHE_TTL_SECONDS` | `300` — how long to cache the public key before re-fetching |

---

## Key rotation

```sh
# 1. Regenerate the RSA key pair and update ACCESS_KEY_ID in auth.env
bash init.sh --rotate-keys

# 2. Restart the auth service (picks up new private key + kid)
docker compose up -d auth_user_service

# 3. Consumers self-update — no restart needed
```

Old tokens remain valid until they expire. After `JWKS_CACHE_TTL_SECONDS` the consumer cache refreshes; tokens with the old `kid` will then fail verification.

---

## Volumes

| Path | Purpose |
| --- | --- |
| `./keys` | RSA key pair (mounted read-only into auth container) |
| `./db_data` | Persistent PostgreSQL data |
| `./redis/redis_data` | Persistent Redis snapshots |
| `./prometheus/data` | Prometheus TSDB |
| `./grafana/data` | Grafana dashboards and state |
| `./shared_migrations` | Alembic migration files (auto-created, shared between services) |

---

## Common operations

```sh
# Start in background
docker compose up -d

# Follow logs for all services
docker compose logs -f

# Follow logs for auth service
docker compose logs -f auth_user_service

# Verify JWKS endpoint
curl http://localhost:9000/user/.well-known/jwks.json | python -m json.tool

# Full reset — stops containers and wipes the database
bash init.sh --reset-db
```

---

## Live testing

Run the live test suite against this stack (requires the stack to be up):

```sh
# From the repo root
pytest -m live_asymmetric --no-cov   # RS256/ES256-specific attacks (JWKS, kid confusion)
pytest -m live_stateful --no-cov     # Token revocation guarantees
pytest -m live_security --no-cov     # Universal attack categories
```

Manual smoke test:

```sh
curl http://localhost:9000/user/health/
# Expected: {"status":"ok","token_mode":"stateful","redis":"ok","database":"ok",...}
```

---

## Troubleshooting

**Auth service fails to start — key file not found** — ensure you ran `bash init.sh` and that `keys/private.pem` and `keys/public.pem` both exist.

**JWKS endpoint returns empty `keys` array** — the service started before the key files were mounted. Restart: `docker compose restart auth_user_service`.

**Services fail to start immediately** — `auth_user_service` waits for PostgreSQL (`pg_isready`). PostgreSQL typically initialises in 10–20 s on first boot.

**`changethis` rejection on startup** — replace all `changethis` values in `.env`, `auth.env`, and `api.env`.

**Grafana shows no data** — confirm `METRICS_ENABLED=true` in `auth.env`, then make at least one request to generate metrics. Check Prometheus targets at `http://localhost:9090/targets`.

**Port conflict** — identify the conflicting process with `netstat -ano | findstr <PORT>` (Windows) or `lsof -i :<PORT>` (Mac/Linux).

---

> [Docker Compose examples](../README.md) · [Repository root](https://github.com/mano8/fa-auth-m8/tree/main)
