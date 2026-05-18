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

### 1. Copy and edit the env files

```sh
cp .env.example .env
cp auth.env.example auth.env
cp api.env.example api.env
```

Open `.env` and replace every `changethis` (DB credentials, Redis password).

Open `auth.env` and replace every `changethis`:

```ini
REFRESH_SECRET_KEY="<generate>"     # refresh tokens remain HS256 symmetric
PRIVATE_API_SECRET="<generate>"     # for internal service-to-service calls
TOKENS_ENCRYPTION_KEY="<generate>"  # encrypts refresh token payloads at rest
```

Leave `ACCESS_KEY_ID=changethis_hex_kid` as-is — `init.sh` derives it automatically
from the generated key fingerprint and writes the correct value into `auth.env`.

`api.env` requires no changes. The `JWKS_URI` already points to the auth service's
JWKS endpoint over the internal Docker network.

### 2. Generate RSA key pair + TLS certificates

```sh
bash init.sh
```

> **Windows:** `init.sh` requires bash — use **Git Bash** (included with Git for Windows) or **WSL**.

This generates `keys/private.pem` and `keys/public.pem`, derives a stable `kid` from
the DER fingerprint, writes `ACCESS_KEY_ID` into `auth.env`, and generates the
self-signed TLS certificate for Traefik. Keep `keys/private.pem` out of version
control (it is already in `.gitignore`).

### 3. Start

```sh
docker compose up --build
```

Migrations run automatically on first boot. The superuser defined in `.env` is created
if it does not exist.

---

## How JWKS works in this stack

```text
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

- **Key rotation**: run `bash init.sh --rotate-keys` to regenerate the key pair and
  update `ACCESS_KEY_ID` in `auth.env`, then restart auth. Old tokens keep working until
  they expire. Consumers fetch the new public key automatically on the first request with
  an unknown `kid`.
- **No manual key sync**: consumers never need the private key or a pre-shared copy of
  the public key.

The JWKS endpoint is public (no auth required) at:

```text
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

## Database isolation

This stack defaults to **Scenario 2** (per-service isolation): `auth_db` and `api_db`
are created as separate databases with separate users on first volume init. To switch
to a single shared DB or add more services, see the scenario blocks in `.env.example`
and the [database isolation guide](../README.md#database-isolation).

Database provisioning runs **once** on first volume creation. If `.env` DB config
changes after the volume exists, reset with `bash init.sh --reset-db`.

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

**1. Regenerate the key pair and update `ACCESS_KEY_ID`:**

```sh
bash init.sh --rotate-keys
```

This overwrites `keys/private.pem` and `keys/public.pem` with a fresh RSA pair and
derives a new `kid` from the DER fingerprint, writing it to `ACCESS_KEY_ID` in
`auth.env`.

**2. Restart the auth service:**

```sh
docker compose up -d --build auth_user_service
```

**3. Consumers self-update** — no restart needed. On the first request carrying the
new `kid`, each consumer fetches the updated JWKS endpoint automatically.

Tokens issued with the old `kid` remain valid until they expire. After
`JWKS_CACHE_TTL_SECONDS` the cache refreshes; since the old `kid` no longer appears
in the JWKS response, those tokens will then fail verification.

Tokens issued with the old `kid` remain valid until they expire and are verified using
the old cached public key. After their TTL (`JWKS_CACHE_TTL_SECONDS`) the cache is
refreshed; since the old `kid` no longer appears in the JWKS response, those tokens
will then fail verification.

---

## Volumes

| Path | Purpose |
| --- | --- |
| `./keys` | RSA key pair (mounted read-only into auth container) |
| `./db_data` | Persistent MariaDB data |
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

# Full reset — stops containers and wipes the database (prompts for confirmation)
# Note: Prometheus and Grafana data in ./prometheus/data and ./grafana/data persist.
# Delete those directories manually if you also want to reset observability state.
bash init.sh --reset-db
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
