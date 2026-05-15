# RS256_m8

**MariaDB 12** + **RS256 asymmetric token signing** + stateful token mode +
**Prometheus & Grafana** observability.

Access tokens are signed with a private RSA key (auth service only) and verified with
the corresponding public key (all consumer services). Consumers discover the public key
automatically via the **JWKS endpoint** — no manual key distribution required.

**Choose this when:**

- You have multiple consumer services that need to verify tokens independently.
- You want zero-downtime key rotation: rotate the RSA key pair and consumers pick up
  the new public key on the next unknown `kid` without a restart.
- You are building toward a production-grade setup.

---

## How RS256 differs from HS256

| Aspect | HS256 (symmetric) | RS256 (asymmetric) |
| --- | --- | --- |
| Signing key | Shared secret (both sign and verify) | Private key signs, public key verifies |
| Key distribution | Every service needs the secret | Consumers fetch public key via JWKS |
| Key rotation | Requires coordinated secret update | Auth rotates private key; consumers auto-refresh |
| `kid` header in JWT | Not used | Stable identifier linking JWT to the public key |
| `ACCESS_SECRET_KEY` | Required | **Not used** — omit it |

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

### 1. Generate RSA key pair

The auth service needs a private key to sign tokens. The consumer verifies using the
public key fetched from the JWKS endpoint — you do **not** need to copy the public key
anywhere manually.

```sh
# Run from this directory (RS256_m8/)
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

The `keys/` directory is mounted read-only into the auth container at `/opt/keys/`.
Keep `keys/private.pem` out of version control (it is already in `.gitignore`).

### 2. Copy and edit the env files

```sh
cp .env.example .env
cp auth.env.example auth.env
cp api.env.example api.env
```

Open `.env` and replace every `changethis`:

```ini
FIRST_SUPERUSER="admin@example.com"
FIRST_SUPERUSER_PASSWORD="a-strong-password"

# No ACCESS_SECRET_KEY for RS256 — leave it absent
ACCESS_KEY_ID="my-key-v1"          # stable identifier embedded as "kid" in every JWT
REFRESH_SECRET_KEY="<generate>"    # refresh tokens remain HS256 symmetric

DB_USER="myuser"
DB_PASSWORD="<generate>"
DB_ROOT_PASSWORD="<generate>"

REDIS_PASSWORD="<generate>"
```

`ACCESS_KEY_ID` is a stable string you choose (e.g. `"prod-2025-01"`). It is embedded
as the `kid` header in every JWT. When you rotate keys, update this value and consumers
will automatically re-fetch the new public key from JWKS.

Open `auth.env` and replace:

```ini
PRIVATE_API_SECRET="<generate>"     # for internal service-to-service calls
TOKENS_ENCRYPTION_KEY="<generate>"  # encrypts refresh token payloads at rest
```

`api.env` requires no changes. The `JWKS_URI` already points to the auth service's
JWKS endpoint over the internal Docker network.

### 3. Start

```sh
docker compose up --build
```

Migrations run automatically on first boot. The superuser defined in `.env` is created
if it does not exist.

---

## How JWKS works in this stack

```
Consumer receives JWT with header: {"alg": "RS256", "kid": "my-key-v1"}
         │
         ▼
Is "my-key-v1" in local cache?
   Yes → verify signature → done
   No  → GET http://auth_user_service:8000/user/.well-known/jwks.json
              │
              ▼  (returns all public keys indexed by kid)
         Cache result for JWKS_CACHE_TTL_SECONDS (default: 300 s)
         Verify signature → done
```

This means:

- **Key rotation**: generate a new key pair, update `ACCESS_KEY_ID` in `.env`, restart
  auth. Old tokens (with the old `kid`) keep working until they expire. New tokens use
  the new key. Consumers fetch the new public key automatically on the first request with
  an unknown `kid`.
- **No manual key sync**: consumers never need the private key or a pre-shared copy of
  the public key.

The JWKS endpoint is public (no auth required) at:

```
http://localhost:9000/user/.well-known/jwks.json
```

---

## Token mode: stateful

This stack defaults to `TOKEN_MODE=stateful`:

| Mode | Access token validated by | Refresh token | Redis round-trip per request |
| --- | --- | --- | --- |
| `stateless` | JWT signature only | JWT signature only | No |
| `hybrid` | JWT signature only | Redis allowlist | No |
| **`stateful`** | **JWT signature + Redis blacklist** | **Redis allowlist** | **Yes** |

In `stateful` mode:

- **Login** → writes `rt:<jti>` to Redis and creates a `client_session` DB row.
- **Logout** → immediately invalidates the access token via Redis blacklist, regardless
  of its remaining lifetime.

---

## Observability

### Grafana — `http://localhost:3000`

Pre-provisioned with a Prometheus datasource. Default credentials: `admin` / `admin`.

### Prometheus — `http://localhost:9090`

Scrapes `/user/metrics` from the auth service (`METRICS_ENABLED=true` in `auth.env`).

---

## URLs

| What | URL |
| --- | --- |
| Auth API | `http://localhost:9000/user/` |
| Auth interactive docs | `http://localhost:9000/user/docs` |
| JWKS endpoint | `http://localhost:9000/user/.well-known/jwks.json` |
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
| `ACCESS_TOKEN_ALGORITHM` | `RS256` | Do not change to `HS256` here — use a different stack |
| `REFRESH_TOKEN_ALGORITHM` | `HS256` | Refresh tokens remain symmetric |
| `ACCESS_KEY_ID` | — | Stable `kid` value embedded in every JWT header |
| `REFRESH_SECRET_KEY` | — | HMAC secret for refresh tokens |
| `TOKEN_MODE` | `stateful` | `stateless` / `hybrid` / `stateful` |
| `SELECTED_DB` | `Mysql` | `Mysql` or `Postgres` |
| `DB_HOST` | `m8_db` | Docker service name — do not change for compose |

### `auth.env` — auth service only

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `issuer` — signs tokens with the RSA private key |
| `ACCESS_PRIVATE_KEY_FILE` | `/opt/keys/private.pem` — path inside the container |
| `ACCESS_PUBLIC_KEY_FILE` | `/opt/keys/public.pem` — path inside the container |
| `PRIVATE_API_SECRET` | Secret for `X-Internal-Token` header (service-to-service calls) |
| `TOKENS_ENCRYPTION_KEY` | Fernet key for encrypting refresh token payloads in Redis |
| `METRICS_ENABLED` | `true` — exposes `/user/metrics` for Prometheus to scrape |

### `api.env` — consumer service only

| Variable | Notes |
| --- | --- |
| `AUTH_SERVICE_ROLE` | `consumer` — verifies tokens via JWKS, does not sign them |
| `JWKS_URI` | `http://auth_user_service:8000/user/.well-known/jwks.json` |
| `JWKS_CACHE_TTL_SECONDS` | `300` — how long to cache the public key before re-fetching |

---

## Key rotation procedure

1. Generate a new key pair in `keys/`:
   ```sh
   openssl genrsa -out keys/private.pem 2048
   openssl rsa -in keys/private.pem -pubout -out keys/public.pem
   ```
2. Update `ACCESS_KEY_ID` in `.env` to a new value (e.g. `"my-key-v2"`).
3. Restart the auth service:
   ```sh
   docker compose up -d --build auth_user_service
   ```
4. Consumer services pick up the new public key automatically on the first request
   carrying the new `kid`. No consumer restart needed.

Tokens issued with the old `kid` remain valid until they expire and are verified using
the old cached public key. After their TTL (`JWKS_CACHE_TTL_SECONDS`) the cache is
refreshed; since the old `kid` no longer appears in the JWKS response, those tokens
will then fail verification.

---

## Volumes

| Path | Purpose |
| --- | --- |
| `./keys` | RSA key pair (mounted read-only into auth container) |
| `./mysql_db` | Persistent MariaDB data |
| `./redis/redis_data` | Persistent Redis snapshots |
| `./prometheus/data` | Prometheus TSDB |
| `./grafana/data` | Grafana dashboards and state |
| `./shared_migrations` | Alembic migration files (auto-created, shared between services) |
| `../../../auth_user_service` | Live source mount — Python changes apply without rebuild |

---

## Common operations

```sh
# Start in background
docker compose up -d --build

# Follow logs for auth service
docker compose logs -f auth_user_service

# Verify JWKS endpoint is serving the public key
curl http://localhost:9000/user/.well-known/jwks.json | python -m json.tool

# Stop (keeps volumes and data)
docker compose stop

# Full reset — removes all stored data
docker compose down -v
```

---

## Troubleshooting

**Auth service fails to start — key file not found** — ensure you ran the `openssl`
commands in step 1 and that `keys/private.pem` and `keys/public.pem` both exist.

**JWKS endpoint returns empty `keys` array** — the service started before the key files
were mounted. Restart the auth service: `docker compose restart auth_user_service`.

**Consumer rejects valid tokens** — confirm `ACCESS_KEY_ID` in `.env` matches the `kid`
value in your JWTs. Decode a token at `https://jwt.io` and compare the `kid` header.

**`changethis` rejection on startup** — replace all `changethis` values in `.env`
and `auth.env`. `ACCESS_SECRET_KEY` must be absent (not set to `changethis`) for RS256.

**Port conflict** — identify the conflicting process with `netstat -ano | findstr <PORT>`
(Windows) or `lsof -i :<PORT>` (Mac/Linux) and stop it.
