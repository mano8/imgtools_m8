# Docker Compose Examples

Four ready-to-run stacks for local development. Each runs the same services with different
database engines, token modes, and observability options.

## Which stack should I use?

| Stack | Database | Token mode | Monitoring | Best for |
| --- | --- | --- | --- | --- |
| [local_mysql_m8](local_mysql_m8/) | MariaDB | hybrid | — | Fastest start, everyday dev |
| [dev_postgres_m8](dev_postgres_m8/) | PostgreSQL 16 | stateful | — | PostgreSQL projects |
| [stateful_m8](stateful_m8/) | MariaDB | stateful | Prometheus + Grafana | Testing metrics & dashboards |
| [RS256_m8](RS256_m8/) | MariaDB | stateful | Prometheus + Grafana | Asymmetric signing, JWKS, key rotation |

**Start here →** [local_mysql_m8](local_mysql_m8/) if you just want things running quickly.  
**Use RS256_m8** if you need multiple consumer services that verify tokens independently,
or when building toward a production setup.

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
| `9090` | `127.0.0.1` | Prometheus (stateful_m8, RS256_m8 only) |
| `3000` | `127.0.0.1` | Grafana (stateful_m8, RS256_m8 only) |

Port `9000` is the one you'll use most in development — all API requests go through it.
