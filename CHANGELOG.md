# Changelog

All notable changes to `fa-auth-m8` will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [0.6.1] - 2026-05-16

### Fixed

- **Idempotent superuser seed**: `initial_user_db` now guards on the presence of any superuser in the database instead of looking up the specific bootstrap email. On subsequent `compose up` runs the seed is skipped entirely and a log line confirms it — `FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD` remain required by config but are never applied again after the first run.

---

## [0.6.0] - 2026-05-14

### Security

- **Atomic refresh token rotation** via Lua script — eliminates the double-spend race condition on concurrent refresh requests.
- **Atomic PKCE code redemption** using Redis `GETDEL` — closes token-code reuse on the Google OAuth callback.
- **Real client IP attribution behind Traefik**: coordinated fix across Traefik `forwardedHeaders.trustedIPs`, Uvicorn `--proxy-headers --forwarded-allow-ips`, and `_client_ip()` in `routes/login.py`.  Audit logs and rate-limit keys now record the real peer address instead of the Docker bridge IP.
- **Secure-by-default API binding**: Traefik port 9000 now binds to `${API_BIND_IP:-127.0.0.1}`, preventing accidental public exposure on cloud hosts.
- **HSTS opt-in**: `Strict-Transport-Security` is present but commented out in all `traefik/dynamic_conf.yml` files with an explicit warning — must be intentionally enabled after confirming stable TLS.
- **`iss`/`aud` JWT claim enforcement** (opt-in): set `TOKEN_ISSUER` / `TOKEN_AUDIENCE` in both services; issued tokens embed the claims and validation requires an exact match, preventing cross-service token reuse.
- **JWKS endpoint + `kid` header** (`routes/jwks.py`): `GET {API_PREFIX}/.well-known/jwks.json` returns the active public key in JWK Set format. Access tokens now carry a `kid` header for RS256/ES256 deployments. HS256 returns `{"keys": []}`.
- **`JwksKeyResolver`** (SDK v0.5.0): fetches the JWKS endpoint, caches by `kid` for `JWKS_CACHE_TTL_SECONDS` (default 300 s), and refreshes on cache miss — supporting zero-downtime key rotation.
- **`build_access_validator()` factory** (SDK v0.4.2): consolidates duplicated validator construction across both services (algorithm selection, key choice, iss/aud wiring).
- **`AccessTokenBlacklist`** (SDK v0.4.2): thin Redis wrapper for JTI revocation checks, shared by auth and consumer services using the same `"jwt:blacklist:"` namespace.
- **Consumer JTI blacklist enforcement** (`examples/fastapi_service`): `get_current_user` now checks `AccessTokenBlacklist` before returning the user; Redis pool replaced the per-request connection to close a fail-open bypass under connection exhaustion.
- **Google OAuth refresh JTI registration**: `google_auth_callback` now registers the refresh JTI in `RedisRefreshStore`, matching the password-login flow and fixing "Token revoked or reused" on first OAuth refresh.
- **HTTPException swallowing fix**: broad `except Exception` blocks in `routes/profile.py`, `routes/sessions.py`, and `routes/users.py` were silently converting `HTTPException` (404/403/409) into 500 responses — re-raise added before the generic handler.
- **Avatar upload crash fix**: `update_avatar` raised `pydantic.ValidationError` for invalid MIME type, extension, or oversized file → 500. Replaced with `HTTPException(400/413)`.
- **Timing-attack prevention on login**: a module-level `_DUMMY_HASH` constant ensures constant-time response (~185 ms) regardless of whether the email exists.
- **Redis key namespace hardening** (`LoginRateLimiter._key`): raw email was used verbatim as a Redis key; non-printable characters are now stripped and keys are capped at 255 chars.
- **Live red-team test suite** (`tests/live/test_redteam_rs256.py`): 85-test live integration suite against the RS256_m8 Compose stack, covering 12 attack categories. Run with `pytest -m live`.

### Added

- **`GET {API_PREFIX}/health/`** — unauthenticated health endpoint reporting `status`, `token_mode`, `effective_mode`, `redis`, `database`, `revocation_available`, `rate_limiting_available`, and `degraded_since`.
- **Prometheus metrics** via `auth_sdk_m8.observability` (enabled with `METRICS_ENABLED=true`):
  - `auth_user_service` exposes `GET /user/metrics` with auth-specific counters (`login_attempts_total`, `token_refresh_total`, `logout_total`, `token_validation_failures_total`, `oauth_attempts_total`).
  - `examples/fastapi_service` exposes `GET /fastapi/metrics` with HTTP traffic/performance counters.
- **`examples/docker_compose/stateful_m8/`** — Compose stack: Traefik + MariaDB + Redis + auth service + example service + Prometheus + Grafana.
- **`examples/docker_compose/RS256_m8/`** — RS256 variant with asymmetric signing, JWKS distribution, and Prometheus + Grafana. Includes `keys/generate_keys.sh`.
- **`examples/docker_compose/dev_postgres_m8/`** — PostgreSQL development stack with Traefik and Redis.
- **Lifespan startup checks** (`main.py`): logs `CRITICAL` at startup when Redis is unreachable but required by `TOKEN_MODE`, or when the database is unreachable.
- **`check_config_health(settings, logger)`** from SDK: both services call this at startup to surface configuration warnings (JWKS_URI on HS256, missing key material, Redis absent in stateful/hybrid mode) before the first request.
- **`RedisRefreshStore`** (`core/client.py`): allowlist-backed refresh token store. Rotation is atomic; absent key = revoked, which is safe-fail on Redis flush.
- **Global exception handlers** in `main.py`: `SQLAlchemyOperationalError` and `RedisConnectionError` return structured 503 responses as a backstop for any infra error escaping route-level handlers.
- **`TOKEN_ISSUER` / `TOKEN_AUDIENCE` / `ACCESS_KEY_ID` / `JWKS_URI` / `JWKS_CACHE_TTL_SECONDS`** added to `CommonSettings` (SDK v0.5.0) and inherited by both services.
- **Alembic migrations** for `stateful_m8`, `RS256_m8`, and `dev_postgres_m8` stacks.
- **Security test suite** (`tests/security/`): JWT security, Redis resilience, refresh lifecycle, input sanitisation, JWKS endpoint, OAuth adversarial, iss/aud validation, session-chain invalidation, exception handling, client IP — ~1 200 lines across 10 modules.

### Changed

- `TOKEN_MODE` now controls Redis pool creation: the pool is only initialised when `TOKEN_MODE != "stateless"`.
- UUID handling unified: `UUIDChar` TypeDecorator removed; all models use SQLModel `Uuid` type.
- `_access_validator` construction in both services simplified to `build_access_validator(settings, hooks)`.
- `get_redis_client()` now `ping()`s before returning; returns `None` on failure so `if redis is not None:` guards correctly reflect live connectivity.
- Google OAuth PKCE routes explicitly return `503` when Redis is unavailable instead of crashing with 500.
- `auth_user_service/core/deps.py`: `_access_validation_secret()` helper removed.
- `examples/fastapi_service/core/deps.py`: `TokenValidator` promoted to module-level singleton; `RedisDep` added; full rewrite aligned with auth service patterns.
- Logout now deletes the DB session in addition to clearing Redis.

### Breaking

- Existing refresh sessions are invalidated on first deploy — JTIs are not pre-populated in the new Redis allowlist; users must re-login once after upgrading.
- `auth-sdk-m8` must be `>=0.5.0`. Reinstall before deploying.

---

## [0.3.0] - 2026-05-07

### Added

- Refresh token rotation: old JTI is revoked in Redis before new tokens are issued, acting as a compromise signal.
- `examples/fastapi_service/`: reference FastAPI consumer service using `TokenValidator` and dependency injection.
- `examples/docker_compose/local_mysql_m8/`: ready-to-run Compose stack (Traefik, MariaDB, Redis, auth service, example service).

### Changed

- `_access_validator` promoted to module-level singleton in `auth_user_service/core/deps.py` (was re-created per-request).
- `LoginRateLimiter` receives the injected `RedisDep` directly.
- Logout reads accurate expiry from `payload.exp` instead of a fixed offset.
- `refresh_token_hash` is now updated in the session-update branch in `client_sessions.py`.
- Traefik pinned to stable `v3.3`; Redis pinned to `7.4-alpine`; healthchecks added for MariaDB and Redis; `depends_on` uses `condition: service_healthy`.

### Fixed

- `POST /login/test-token/` was double-prefixed as `/login/login/test-token/` — corrected.
- `get_dash_users_stats` was constructing `UsersActivity` without required `nb_users` field.

---

## [0.2.0] - 2026-05-06

### Added

- Private inter-service API (`/private/`) protected by `X-Internal-Token` header and Docker network isolation.
- Google OAuth2 login flow with PKCE support.
- Profile endpoints: read/update own profile, upload avatar.
- Session management endpoints: list active sessions, revoke individual sessions.
- Login rate limiting per email address via Redis (15-minute lockout after repeated failures).
- Dashboard activity endpoints (superuser only).
- Alembic migrations run and superuser seeded automatically on container start.

### Changed

- Switched from `SECRET_KEY` to separate `ACCESS_SECRET_KEY` / `REFRESH_SECRET_KEY`.
- `auth-sdk-m8` dependency bumped to `>=0.2.0`.

---

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
