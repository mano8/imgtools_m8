# Docker Compose Examples

Five ready-to-run stacks, each targeting a distinct use case. Each runs the same two application services with different infrastructure and configuration.

---

## Summary

- [Which stack should I use?](#which-stack-should-i-use)
- [Common architecture](#common-architecture)
- [Token modes](#token-modes)
- [Quick start](#quick-start)
- [Environment file system](#environment-file-system)
- [Database isolation](#database-isolation)
- [Shared migrations](#shared-migrations)
- [Ports](#ports-same-for-all-stacks)
- [Live testing](#live-testing)

---

## Which stack should I use?

| Stack | Database | Algorithm | Token mode | Secrets | Monitoring | Hardening | Best for |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [quickstart_m8](quickstart_m8/) | MariaDB | HS256 | `stateful` | env file | — | — | **Start here** — fastest onboarding |
| [postgres_m8](postgres_m8/) | PostgreSQL 16 | HS256 | `stateful` | env file | — | — | PostgreSQL projects |
| [rs256_m8](rs256_m8/) | MariaDB | RS256 | `hybrid` | env file | — | — | Asymmetric signing + JWKS |
| [metrics_m8](metrics_m8/) | PostgreSQL 16 | HS256 | `stateful` | env file | Prometheus + Grafana | — | Metrics dashboards |
| [hardened_m8](hardened_m8/) | PostgreSQL 16 | RS256 | `stateful` | env file | Prometheus + Grafana | container + network | Hardened posture without Vault |
| [vault_m8](vault_m8/) | PostgreSQL 16 | RS256 | `stateful` | **HashiCorp Vault** | Prometheus + Grafana | container + network | Hardened + secrets manager |

**Decision guide:**

- **Just want things running** → [quickstart_m8](quickstart_m8/)
- **Need PostgreSQL without monitoring** → [postgres_m8](postgres_m8/)
- **Asymmetric signing / multiple consumers** → [rs256_m8](rs256_m8/) or [hardened_m8](hardened_m8/)
- **Metrics and dashboards** → [metrics_m8](metrics_m8/)
- **Container hardening + observability** → [hardened_m8](hardened_m8/) — Docker Hub image, read-only rootfs, network segmentation
- **Secrets manager (Vault)** → [vault_m8](vault_m8/) — credentials never live in plain env files
- **Stateless mode** → start from [quickstart_m8](quickstart_m8/) and set `TOKEN_MODE=stateless` in `auth.env`

---

## Common architecture

All stacks share the same service layout:

```text
Browser / Frontend
       │
       ▼
  Traefik :9000  ──────────────────────────────┐
       │                                        │
       ▼  /user/*                               ▼  /fastapi/*
auth_user_service :8000            fastapi_full :8000
       │                                        │
       └──────────┬─────────────────────────────┘
                  │
          ┌───────┴────────┐
          ▼                ▼
        m8_db          redis_cache
   (MariaDB / PG)      (Redis 7.4)

(metrics_m8, hardened_m8, and vault_m8 also include Prometheus + Grafana)
```

Traefik is the single entry point. Both application services sit on an internal Docker network (`m8_app_network`) and are not directly reachable from the host.

---

## Token modes

Set `TOKEN_MODE` in `auth.env` to control how access tokens are validated:

| Mode | How it works | Redis for JWT | Google OAuth | Use case |
| --- | --- | --- | --- | --- |
| `stateless` | Verify JWT signature only — no server-side state | No | ❌ disabled | Maximum scalability, no revocation needed |
| `hybrid` | JWT access token + Redis-stored refresh allowlist | Refresh only | ✅ | Good balance: scalable access + revocable refresh |
| `stateful` | Every request checks Redis blacklist | Yes | ✅ | Instant logout guarantee |

> **Stateless limitation:** Google OAuth requires Redis for the PKCE code-exchange flow and is
> disabled when `TOKEN_MODE=stateless`. All other features work normally.
>
> **Hybrid trade-off:** A stolen access token remains valid for its full lifetime after logout.
> Refresh tokens are revoked immediately. Use `stateful` if instant access token revocation is required.

---

## Quick start

Every stack follows the same four steps:

```sh
# 1. Copy env files and fill in all secrets (replace every 'changethis')
cp auth.env.example auth.env
cp api.env.example api.env

# 2. Generate keys (RS256/ES256 stacks) and TLS certificates
bash init.sh

# 3. (Optional) Reset the database volume if it already exists
# bash init.sh --reset-db    # prompts for confirmation; use --yes for CI

# 4. Bring up the stack — DB is provisioned automatically on first boot
docker compose up -d --build
```

> **Windows:** `init.sh` requires bash — use **Git Bash** (included with Git for Windows) or **WSL**.

Generate secret values with:

```sh
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

To rotate cryptographic keys without reinitializing: `bash init.sh --rotate-keys`.

---

## Environment file system

Each stack uses **two env files** for the application services. Copy the `.example` files and fill in your values:

```text
auth.env      ← auth_user_service: algorithm, token mode, secrets, DB/Redis config, expiry
api.env       ← fastapi_full: consumer role, token validation config, JWKS URI if RS256/ES256
```

Some stacks also use a shared `.env` file at the stack root for infrastructure variables (DB root password, Redis password) that are read directly by the database container's init script.

Generate secrets with:

```sh
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## Database isolation

`init-db.sh` runs inside the DB container on first volume creation and provisions databases automatically. Choose one model:

**Scenario 1 — single shared DB** (simplest):

```ini
DB_USER=myuser
DB_PASSWORD=a-strong-password
DB_NAME=myapp
```

All services share one database and one user.

**Scenario 2 — per-service isolation** (default in all stacks):

```ini
AUTH_DB_USER=auth_user   AUTH_DB_PASSWORD=...  AUTH_DB_NAME=auth_db
API_DB_USER=api_user     API_DB_PASSWORD=...   API_DB_NAME=api_db
```

Each service gets its own database and credentials. `init-db.sh` creates them automatically.

**Scenario 3 — N-service isolation** (extend Scenario 2 freely):

```ini
WORKER_DB_USER=worker_user  WORKER_DB_PASSWORD=...  WORKER_DB_NAME=worker_db
SEARCH_DB_USER=search_user  SEARCH_DB_PASSWORD=...  SEARCH_DB_NAME=search_db
```

Add any `PREFIX_DB_{USER,PASSWORD,NAME}` triplet. Prefixes must be `UPPERCASE`, start with a letter, and use only `[A-Z0-9_]`. No compose edits needed — the DB container sees all `.env` vars via `env_file:` and discovers triplets automatically.

**Validation**: `init-db.sh` detects and rejects: missing/empty fields, duplicate `DB_NAME` or `DB_USER` across prefixes (silent isolation collapse), invalid identifier characters, and mixed bare+prefixed configuration. Weak or reused passwords produce warnings without blocking startup.

**Stale volume**: Database provisioning runs **once** on first volume creation. If DB config changes after the volume exists, reset with `bash init.sh --reset-db`.

---

## Shared migrations

The `shared_migrations/` directory is created automatically on first start. It holds Alembic version files for both the auth schema and the application schema:

```text
shared_migrations/
├── auth_user/versions/   ← users, sessions, API keys, rate limits
└── m8_app/versions/      ← your application tables
```

Migrations run automatically every time the containers start. If you switch stacks, the migration history is preserved across restarts because the directory is mounted as a volume.

---

## Ports (same for all stacks)

| Port | Bound to | What |
| --- | --- | --- |
| `8000` | `0.0.0.0` | Traefik HTTP — public |
| `4430` | `0.0.0.0` | Traefik HTTPS — public |
| `9000` | `127.0.0.1` | API services entry (override with `API_BIND_IP` in auth.env) |
| `8080` | `127.0.0.1` | Traefik dashboard |
| `3306` / `5432` | `127.0.0.1` | Database |
| `6379` | `127.0.0.1` | Redis |
| `8200` | `127.0.0.1` | HashiCorp Vault UI/API (`vault_m8` only) |
| `9090` | `127.0.0.1` | Prometheus (`metrics_m8`, `hardened_m8`, `vault_m8`) |
| `3000` | `127.0.0.1` | Grafana (`metrics_m8`, `hardened_m8`, `vault_m8`) |

Port `9000` is the one you'll use most in development — all API requests go through it.

---

## Live testing

The repo includes a modular live test suite in `tests/live/` that runs against any running stack. Tests are automatically skipped when the running stack algorithm or token mode does not match.

```sh
# From the repo root — run against any stack
pytest -m live --no-cov

# Target specific algorithm or mode
pytest -m live_asymmetric --no-cov    # RS256 / ES256 stacks
pytest -m live_hs256 --no-cov         # HS256 stacks
pytest -m live_stateful --no-cov      # TOKEN_MODE=stateful
pytest -m live_hybrid --no-cov        # TOKEN_MODE=hybrid
pytest -m live_stateless --no-cov     # TOKEN_MODE=stateless
```

For a manual smoke test, check the health endpoint after `docker compose up`:

```sh
curl http://localhost:9000/user/health/
# Expected: {"status":"ok","token_mode":"...","redis":"ok","database":"ok",...}
```

Then open `http://localhost:9000/user/docs` in a browser (requires `SET_DOCS=true` in `auth.env`).

---

> Back to [repository root](https://github.com/mano8/fa-auth-m8/tree/main)
