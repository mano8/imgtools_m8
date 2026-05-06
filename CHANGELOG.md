# Changelog

All notable changes to `fa-auth-m8` will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-05-07

### Added

- **Refresh token rotation** (`routes/login.py`): the old JTI is now revoked in Redis
  before new tokens are issued on every `/login/refresh-token/` call.  A stolen refresh
  token that has already been used is rejected immediately, acting as a compromise signal.
- **`examples/fastapi_service/`**: a complete reference FastAPI service showing how to
  integrate with `auth_user_service` using `TokenValidator`, dependency injection, and
  Docker Compose.
- **`examples/docker_compose/local_mysql_m8/`**: a ready-to-run Compose stack (Traefik,
  MariaDB, Redis, auth service, example service).

### Changed

- **`auth_user_service/core/deps.py`**: `_access_validator` is now a module-level
  `TokenValidator` instance created once at startup instead of per-request.  `RedisDep`
  is now a proper `Annotated` dependency alias.  Dead code (`token_data = None` pattern)
  removed.  `_access_validator` is exported for use in login routes.
- **`auth_user_service/routes/login.py`**: `_REFRESH_SECRETS` moved to module level
  (avoids re-instantiation on every request).  `LoginRateLimiter` now receives the
  injected `RedisDep` directly.  Logout now reads accurate expiry from `payload.exp`
  instead of using a fixed offset from now.
- **`auth_user_service/services/client_sessions.py`**: `refresh_token_hash` is now
  updated in the session-update branch — previously the stale hash from the previous
  refresh cycle was left in the database.
- **`examples/fastapi_service/core/deps.py`**: migrated from deprecated
  `ComSecurityHelper.decode_access_token` to `TokenValidator` with proper dependency
  injection.
- **`examples/docker_compose/local_mysql_m8/docker-compose.yml`**: Traefik pinned to
  stable `v3.3` (was RC `v3.4.0-rc2`); Redis pinned to stable `7.4-alpine` (was RC
  `8.0-rc1-alpine3.21`); `sleep 1` race condition replaced with a `ping` retry loop;
  healthchecks added for MariaDB and Redis; `depends_on` updated to
  `condition: service_healthy`.

### Fixed

- `POST /login/test-token/` route path was double-prefixed as `/login/login/test-token/`
  because the router already carries `prefix="/login"`.  Corrected to `/login/test-token/`.
- `examples/fastapi_service/controllers/dashboard.py`: `get_dash_users_stats` was
  constructing `UsersActivity` without the required `nb_users` field, causing a
  `ValidationError` at runtime.

## [0.2.0] - 2026-05-06

### Added

- Private inter-service API (`/private/`) protected by `X-Internal-Token` header and
  Docker network isolation.
- Google OAuth2 login flow with PKCE support.
- Profile endpoints: read/update own profile, upload avatar.
- Session management endpoints: list active sessions, revoke individual sessions.
- Login rate limiting per email address via Redis (15-minute lockout after repeated
  failures).
- Dashboard activity endpoints (superuser only).
- Alembic migrations run and superuser is seeded automatically on container start.

### Changed

- Switched from `SECRET_KEY` to separate `ACCESS_SECRET_KEY` / `REFRESH_SECRET_KEY`
  so access and refresh tokens are signed with different secrets.
- `auth-sdk-m8` dependency bumped to `>=0.2.0`; consuming code updated to use the new
  `TokenValidator` / `TokenPolicy` security layer.

## [0.1.0] - 2026-05-01

### Added

- Initial release.
- Email/password login with bcrypt hashing (rounds=12).
- JWT access token + HttpOnly refresh cookie pair.
- Session tracking and JTI revocation via Redis.
- MySQL and PostgreSQL support, switchable via `SELECTED_DB`.
- User management CRUD restricted to superusers.
- Role-based access control (`user`, `admin`, `superuser`).
- Docker multi-stage build with non-root user.
- Traefik reverse-proxy labels.
- VS Code remote debugger support (`VSCODE_DEBUG=true`).
