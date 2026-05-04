# fa-auth-m8

A self-contained FastAPI authentication microservice designed to run as a Docker container via Docker Compose. It provides JWT-based authentication, Google OAuth2, session management, user management, and private inter-service endpoints for any project in the m8 stack.

---

## Features

- Email/password login with bcrypt password hashing
- Google OAuth2 login
- JWT access + refresh token pair (refresh token delivered via HttpOnly cookie)
- Session tracking and revocation via Redis
- Login rate limiting per email (Redis-backed)
- Role-based access control (`user`, `admin`, `superuser`)
- User management CRUD (superuser only)
- Dashboard activity endpoints
- Private inter-service API (protected by shared secret + Docker network isolation)
- MySQL **or** PostgreSQL — switchable via a single env var
- Alembic migrations (auto-generated on first start)
- VS Code remote debugger support

---

## Architecture

```
┌─────────────────────────────────────────┐
│            Docker Compose               │
│                                         │
│  ┌──────────────┐   ┌────────────────┐  │
│  │  auth-service│   │  MySQL/Postgres │  │
│  │  :8000       │──▶│  :3306 / :5432 │  │
│  └──────┬───────┘   └────────────────┘  │
│         │           ┌────────────────┐  │
│         └──────────▶│  Redis :6379   │  │
│                     └────────────────┘  │
└─────────────────────────────────────────┘
```

Other services on the same Docker network can call the private API at `http://auth-service:8000/user/private/`.

---

## API Endpoints

All routes are prefixed with `API_PREFIX` (default `/user`).

| Tag | Method | Path | Description |
| --- | ------ | ---- | ----------- |
| login | POST | `/login/access-token` | Email/password login — returns access token, sets refresh cookie |
| login | POST | `/login/refresh-token/` | Refresh access token from cookie |
| login | POST | `/login/logout/` | Revoke session and clear cookie |
| login | POST | `/login/login/test-token/` | Validate access token |
| oauth-login | * | `/oauth/...` | OAuth2 password-flow endpoints |
| google-auth | GET | `/google/login` | Initiate Google OAuth2 flow |
| google-auth | GET | `/google/callback` | Google OAuth2 callback |
| profile | GET/PATCH | `/profile/me` | Read/update own profile |
| profile | POST | `/profile/me/avatar` | Upload profile avatar |
| sessions | GET/DELETE | `/sessions/...` | List and revoke own sessions |
| users | GET/POST/PATCH/DELETE | `/users/...` | User management (superuser only) |
| dashboard | GET | `/dashboard/users/activity/` | User activity stats (superuser only) |
| private | * | `/private/...` | Inter-service endpoints — Docker network + `X-Internal-Token` header |

Interactive docs are available at `{BACKEND_HOST}{API_PREFIX}/docs` when `SET_DOCS=true`.

---

## Quick Start

### 1. Copy and configure the environment file

```bash
cp auth_user_service/.env.example auth_user_service/.env
```

Edit `.env` and fill in all required values (see [Environment Variables](#environment-variables)).

### 2. Start the stack

```bash
docker compose up --build
```

Alembic migrations run automatically on startup. The first run also seeds the superuser defined by `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`.

### 3. Verify

```
GET http://localhost:8000/user/docs
```

---

## Choosing a Database

Set `SELECTED_DB` in `.env`:

| Value | Driver (sync) | Driver (async) | Default port |
| ----- | ------------- | -------------- | ------------ |
| `Mysql` (default) | `pymysql` | — | 3306 |
| `Postgres` | `psycopg2` | `asyncpg` | 5432 |

Update `DB_HOST`, `DB_PORT`, and `DB_DATABASE` accordingly. Both drivers ship in the container image.

---

## Environment Variables

### Core

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `DOMAIN` | yes | — | Public domain (e.g. `localhost`) |
| `ENVIRONMENT` | yes | — | `local` \| `development` \| `staging` \| `production` |
| `API_PREFIX` | yes | `/user` | URL prefix for all routes |
| `PROJECT_NAME` | yes | — | Project name shown in docs |
| `STACK_NAME` | yes | — | Docker Compose stack slug |
| `BACKEND_HOST` | yes | — | Full backend URL (e.g. `http://127.0.0.1:9000`) |
| `FRONTEND_HOST` | yes | — | Full frontend URL (e.g. `http://localhost:5173`) |
| `BACKEND_CORS_ORIGINS` | yes | — | Comma-separated allowed origins |

### Tokens

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `SECRET_KEY` | yes | — | Session middleware secret |
| `ACCESS_SECRET_KEY` | yes | — | JWT access token signing key |
| `REFRESH_SECRET_KEY` | yes | — | JWT refresh token signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | no | `120` | Refresh token lifetime |
| `REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS` | no | `3600` | Refresh cookie max-age |
| `TOKENS_ENCRYPTION_KEY` | yes | — | Token payload encryption key |

### Database

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `SELECTED_DB` | no | `Mysql` | `Mysql` or `Postgres` |
| `DB_HOST` | yes | — | Database host |
| `DB_PORT` | yes | — | Database port |
| `DB_DATABASE` | yes | — | Database name |
| `DB_USER` | yes | — | Database user |
| `DB_PASSWORD` | yes | — | Database password (strong password required) |
| `DB_ENGINE` | no | `InnoDB` | MySQL storage engine (ignored for Postgres) |
| `DB_CHARSET` | no | `utf8mb4` | MySQL charset (ignored for Postgres) |

### Redis

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `REDIS_HOST` | yes | Redis host |
| `REDIS_PORT` | yes | Redis port |
| `REDIS_USER` | yes | Redis user |
| `REDIS_PASSWORD` | yes | Redis password |

### Auth & OAuth

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `FIRST_SUPERUSER` | yes | Email of the bootstrap superuser |
| `FIRST_SUPERUSER_PASSWORD` | yes | Password of the bootstrap superuser |
| `GOOGLE_CLIENT_ID` | yes | Google OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | yes | Google OAuth2 client secret |
| `PRIVATE_API_SECRET` | yes | Shared secret for private inter-service endpoints (`X-Internal-Token` header) |

### Static / Templates

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `STATIC_BASE_PATH` | yes | Absolute path to static files directory |
| `TEMPLATES_BASE_PATH` | yes | Absolute path to Jinja2 templates directory |

---

## Private API

Endpoints under `/user/private/` are intended for inter-service calls only:

- They **must not** be exposed to the public internet — enforce this at the reverse proxy / Docker network level.
- Every request must include the header `X-Internal-Token: <PRIVATE_API_SECRET>`.

---

## Development

### Run locally (without Docker)

```bash
cd auth_user_service
pip install -r requirements-fastapi.txt
uvicorn auth_user_service.main:app --host 0.0.0.0 --port 8000 --reload
```

### VS Code remote debugging

Set `VSCODE_DEBUG=true` in the container environment. The startup script will launch `debugpy` on port `5678` and wait for the debugger to attach before starting Uvicorn.

### Database migrations

Migrations are generated and applied automatically on container start. To run them manually:

```bash
# Inside the container or with the project on PYTHONPATH
alembic -c auth_user_service/alembic.ini revision --autogenerate -m "description"
alembic -c auth_user_service/alembic.ini upgrade head
```

### Linting & formatting

```bash
ruff format .
ruff check .
ruff check . --fix
```

### Tests

```bash
pytest
```

---

## Dependencies

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLModel](https://sqlmodel.tiangolo.com/) + [Alembic](https://alembic.sqlalchemy.org/)
- [auth-sdk-m8.](https://github.com/mano8/auth-sdk-m8.) — shared schemas, JWT utilities, base controllers
- [Redis](https://redis.io/) — session revocation and rate limiting
- [PyJWT](https://pyjwt.readthedocs.io/) + [passlib](https://passlib.readthedocs.io/) + [cryptography](https://cryptography.io/)
- [google-auth](https://google-auth.readthedocs.io/) — Google OAuth2

---

## License

MIT © Eli Serra
