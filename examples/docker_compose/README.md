# Docker Compose Examples

Four ready-to-run stacks for local development. Each runs the same services with different
database engines, token modes, and observability options.

## Which stack should I use?

| Stack | Database | Token mode | Secrets | Monitoring | Best for |
| --- | --- | --- | --- | --- | --- |
| [local_mysql_m8](local_mysql_m8/) | MariaDB | hybrid | env file | — | Fastest start, everyday dev |
| [dev_postgres_m8](dev_postgres_m8/) | PostgreSQL 16 | stateful | env file | — | PostgreSQL projects |
| [stateful_m8](stateful_m8/) | MariaDB | stateful | env file | Prometheus + Grafana | Testing metrics & dashboards |
| [RS256_m8](RS256_m8/) | MariaDB | stateful | env file | Prometheus + Grafana | Asymmetric signing, JWKS, key rotation |
| [vault_rs256_postgres_m8](vault_rs256_postgres_m8/) | PostgreSQL 16 | stateful | **HashiCorp Vault** | Prometheus + Grafana | Vault secret injection, hardened setup |

**Start here →** [local_mysql_m8](local_mysql_m8/) if you just want things running quickly.  
**Use RS256_m8** if you need asymmetric signing with JWKS and multiple consumer services.  
**Use vault_rs256_postgres_m8** if you need a secrets manager (Vault) so credentials never
live in plain env files — closest to a production-grade hardened setup.

---

## Quick start

Every stack follows the same three steps:

```sh
# 1. copy env files and fill in secrets
cp .env.example .env && cp auth.env.example auth.env && cp api.env.example api.env

# 2. generate keys (RS256/ES* stacks) and TLS certificates
bash init.sh

# 3. bring up the stack — DB is provisioned automatically on first boot
docker compose up -d --build
```

To reset the database: `bash init.sh --reset-db` (prompts for confirmation; use `--yes` for CI).
To rotate cryptographic keys: `bash init.sh --rotate-keys`.

---

## Common architecture

All stacks share the same service layout:

```
Browser / Frontend
       │
       ▼
  Traefik :9000  ──────────────────────────────┐
       │                                        │
       ▼  /user/*                               ▼  /fastapi/*
auth_user_service :8000            fastapi_service :8000
       │                                        │
       └──────────┬─────────────────────────────┘
                  │
          ┌───────┴────────┐
          ▼                ▼
        m8_db          redis_cache
   (MariaDB / PG)      (Redis 7.4)
```

Traefik is the single entry point. Both services sit on an internal Docker network and
are not directly reachable from the host.

---

## Database isolation

`init-db.sh` runs inside the DB container on first volume creation and provisions
databases automatically. Choose one model in `.env`:

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

Add any `PREFIX_DB_{USER,PASSWORD,NAME}` triplet. Prefixes must be `UPPERCASE`,
start with a letter, and use only `[A-Z0-9_]`. No compose edits needed — the DB
container sees all `.env` vars via `env_file:` and discovers triplets automatically.

**Validation**: `init-db.sh` detects and rejects: missing/empty fields, duplicate
`DB_NAME` or `DB_USER` across prefixes (silent isolation collapse), invalid identifier
characters, and mixed bare+prefixed configuration. Weak or reused passwords produce
warnings without blocking startup.

**Stale volume**: Database provisioning runs **once** on first volume creation.
If `.env` DB config changes after the volume exists, reset with `bash init.sh --reset-db`.

---

## Environment file system

Each stack uses **three env files**. Copy the `.example` files and fill in your values:

```
.env          ← shared config: database, Redis, token algorithm, first superuser
auth.env      ← auth_user_service specific settings (API prefix, secrets, expiry)
api.env       ← fastapi_service specific settings (service role, JWKS URI if RS256)
```

Docker Compose reads `.env` automatically and injects the shared variables into both
services via the `environment:` block. Service-specific files are loaded via `env_file:`.
You never need to duplicate a shared variable in both files.

Generate secrets with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## Token modes

Set `TOKEN_MODE` in `.env` to control how access tokens are validated:

| Mode | How it works | Redis required | Use case |
| --- | --- | --- | --- |
| `stateless` | Verify JWT signature only — no server state | No | Maximum scalability |
| `hybrid` | JWT access token + Redis-stored refresh token | Yes | Good balance |
| `stateful` | Every request checks Redis blacklist | Yes | Instant logout guarantee |

> **Note:** `stateless` mode disables Google OAuth (OAuth requires server-side state
> for the code-exchange flow). All stacks here default to `hybrid` or `stateful`
> because Redis is included in every stack.

---

## Shared migrations

The `shared_migrations/` directory is created automatically on first start. It holds
Alembic version files for both the auth schema and the application schema:

```
shared_migrations/
├── auth_user/versions/   ← users, sessions, API keys, rate limits
└── m8_app/versions/      ← your application tables
```

Migrations run automatically every time the containers start. If you switch stacks,
the migration history is preserved across restarts because the directory is mounted as
a volume.

---

## Ports (same for all stacks)

| Port | Bound to | What |
| --- | --- | --- |
| `8000` | `0.0.0.0` | Traefik HTTP — public |
| `4430` | `0.0.0.0` | Traefik HTTPS — public |
| `9000` | `127.0.0.1` | API services entry (override with `API_BIND_IP`) |
| `8080` | `127.0.0.1` | Traefik dashboard |
| `3306` / `5432` | `127.0.0.1` | Database |
| `6379` | `127.0.0.1` | Redis |
| `8200` | `127.0.0.1` | HashiCorp Vault UI/API (vault_rs256_postgres_m8 only) |
| `9090` | `127.0.0.1` | Prometheus (stateful_m8, RS256_m8, vault_rs256_postgres_m8) |
| `3000` | `127.0.0.1` | Grafana (stateful_m8, RS256_m8, vault_rs256_postgres_m8) |

Port `9000` is the one you'll use most in development — all API requests go through it.
