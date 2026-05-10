# Changelog

All notable changes to `fa-auth-m8` will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Security

- **Secure-by-default API port binding** (all three `docker-compose.yml`): Traefik's
  port 9000 was unconditionally bound to `0.0.0.0`, exposing the plaintext API entrypoint
  on all host interfaces including public NICs.  The binding is now
  `${API_BIND_IP:-127.0.0.1}:9000:9000` — localhost-only by default, preventing
  accidental exposure on cloud hosts, CI runners, and multi-tenant machines.
  Set `API_BIND_IP=0.0.0.0` in the compose env to restore LAN / homelab access.
- **HSTS opt-in with explicit warning** (all three `traefik/dynamic_conf.yml`):
  `Strict-Transport-Security` was absent from the security-headers middleware.  Rather
  than enabling it unconditionally, the header is added as a commented-out block with
  a prominent warning: once sent, browsers refuse all HTTP connections to the hostname
  for the configured period — enabling it prematurely in self-hosted / LAN environments
  with self-signed certificates can lock browsers out until the HSTS cache expires.
  Operators must explicitly uncomment `stsSeconds`, `stsIncludeSubdomains`, and
  (optionally) `stsPreload` after confirming TLS is stable and the hostname will remain
  HTTPS-only.
- **Real client IP attribution behind Traefik** (`routes/login.py`,
  `scripts/docker_start.sh`, all three `traefik.yml` configs): audit log fields
  (`ip=`) and rate-limit keys previously captured Traefik's Docker bridge IP
  (`172.x.x.x`) instead of the real client address, making all forensic events,
  abuse correlation, and rate-limit telemetry unreliable.
  Three-layer fix applied:
  1. **Traefik** — `forwardedHeaders.trustedIPs` added to `websecure` and `api`
     entrypoints (`127.0.0.1/32`, `172.16.0.0/12`, `::1/128`).  Traefik will
     now strip any client-supplied `X-Forwarded-For` and replace it with the
     real peer address — preventing IP spoofing.
  2. **Uvicorn** — `--proxy-headers --forwarded-allow-ips=${TRUSTED_PROXY_IPS:-172.16.0.0/12}`
     added to both the production and debugpy startup paths in `docker_start.sh`.
     Uvicorn now reads `X-Forwarded-For` only from the trusted CIDR (Traefik),
     not from arbitrary clients.  Override `TRUSTED_PROXY_IPS` in env to match
     custom deployment subnets; never use `*`.
  3. **Application** — `_client_ip(request)` in `routes/login.py` now reads
     `request.headers["x-forwarded-for"].split(",")[0]` first, falling back to
     `request.client.host` when the header is absent.
- **Google OAuth refresh JTI missing from Redis allowlist** (`routes/google_auth.py`):
  `google_auth_callback` called `create_auth_session` but never registered the refresh JTI in
  `RedisRefreshStore`.  In `stateful`/`hybrid` mode this caused the first refresh after an OAuth
  login to be rejected with "Token revoked or reused" (allowlist miss), while simultaneously
  allowing refresh in degraded mode (Redis down → allowlist skipped → fail-open).  The callback
  now calls `RedisRefreshStore.register(jti, _REFRESH_TTL_SECONDS)` immediately after session
  creation, matching the password-login flow.
- **Consumer service Redis connection leak / fail-open bypass** (`examples/fastapi_service/core/deps.py`):
  `get_redis_client()` created a new `Redis(host=…)` TCP connection on every HTTP request.
  Under connection exhaustion the `except Exception` branch returned `None`, which caused the
  `if redis is not None` guard in `get_current_user` to pass and silently skip the JTI blacklist
  check — a fail-open revocation bypass.  Replaced with a module-level `ConnectionPool`
  (matching `auth_user_service`), so `get_redis_client()` draws from the shared pool and the
  blacklist check is only skipped when Redis is genuinely unreachable.
- **Consumer JTI blacklist enforcement** (`examples/fastapi_service/core/deps.py`): `get_current_user`
  previously never checked the JTI blacklist, leaving revoked access tokens valid at consumer services
  until natural expiry — a silent security gap in `stateful` mode.  `get_current_user` now accepts
  `RedisDep` and calls `AccessTokenBlacklist(redis).is_revoked(payload.jti)` before returning the
  user.  Returns 403 `"Token has been revoked."` when the JTI is in the blacklist.
- **`build_access_validator(settings, hooks=None)` factory** (`auth_sdk_m8/security/factory.py`,
  SDK v0.4.2): consolidates the duplicated validator-construction logic (algorithm selection,
  asymmetric vs symmetric key choice, iss/aud enforcement wiring) into a single canonical function
  exported from `auth_sdk_m8.security`.  Both services now use it instead of copy-pasted boilerplate.
- **`AccessTokenBlacklist`** (`auth_sdk_m8/security/blacklist.py`, SDK v0.4.2): thin Redis wrapper
  exported from `auth_sdk_m8.security`.  Consumer services use it to check revocation using the same
  `"jwt:blacklist:"` prefix written by `auth_user_service`'s `RedisSessionManager.blacklist_jti()`.
- **Opt-in `iss`/`aud` JWT claim enforcement** — `TOKEN_ISSUER` and `TOKEN_AUDIENCE` are now defined
  once in `CommonSettings` (SDK v0.4.2) and inherited by both services.  When set, issued tokens
  embed the corresponding `iss`/`aud` claims and validation requires an exact match — preventing
  token reuse across different services or issuers.  Leave unset for backward-compatible permissive
  validation (default).

- **JWKS endpoint + `kid` header for RS256/ES256** (`routes/jwks.py`, `services/auth.py`,
  `core/security.py`): access tokens issued with asymmetric algorithms now carry a `kid`
  header so consumer services can select the correct public key from the JWKS endpoint.
  A `/.well-known/jwks.json` endpoint is served at `{API_PREFIX}/.well-known/jwks.json`,
  returning the active public key in JWK Set format.  HS256 configurations return
  `{"keys": []}` — the shared secret is never published.  The key ID is taken from
  `ACCESS_KEY_ID` when set; otherwise derived as the first 16 hex chars of the SHA-256
  fingerprint of the public key PEM, making it stable across restarts without configuration.
  Consumer services set `JWKS_URI` and let `build_access_validator` wire up
  `JwksKeyResolver` automatically (SDK v0.5.0).
- **`JwksKeyResolver`** (`auth_sdk_m8/security/jwks_resolver.py`, SDK v0.5.0): fetches
  the JWKS endpoint once, caches keys by `kid` for `JWKS_CACHE_TTL_SECONDS` (default 300 s),
  and refreshes automatically on cache miss (unknown `kid`) to support zero-downtime key
  rotation.  Uses stdlib `urllib.request` — no new runtime dependency.
- **`ACCESS_KEY_ID` / `JWKS_URI` / `JWKS_CACHE_TTL_SECONDS` in `CommonSettings`**
  (SDK v0.5.0): three new optional fields inherited by both services.  `JWKS_URI` enables
  automatic `JwksKeyResolver` wiring in `build_access_validator`; `ACCESS_KEY_ID` pins a
  fixed key ID when explicit rotation labelling is required.

### Added

- **`TOKEN_ISSUER` / `TOKEN_AUDIENCE` in `CommonSettings`** (SDK v0.4.2): both optional fields with
  `None` default are now defined at the SDK base class level.  Services that previously declared them
  locally have had the duplicates removed.
- **`RedisDep`** (`examples/fastapi_service/core/deps.py`): `Annotated[Optional[Redis], Depends(get_redis_client)]`
  type alias added, matching the pattern already used in `auth_user_service`.

### Changed

- **`examples/fastapi_service/core/deps.py`** full rewrite:
  - `get_redis_client()` now returns `Optional[Redis]` with a `ping()` check (previously returned
    bare `Redis` and raised `ConnectionError` on every request when Redis was down).
  - `get_current_user` signature extended with `redis: RedisDep`; checks `AccessTokenBlacklist` in
    stateful mode.
  - `_validator` construction simplified to `build_access_validator(settings, _hooks)` — eliminates
    the private `_access_validation_secret()` helper and manual `TokenValidationConfig` wiring.
  - Unused import `ASYMMETRIC_ALGORITHMS`, `TokenSecret`, `TokenValidationConfig`, `TokenValidator`,
    `SecretStr` removed.
- **`auth_user_service/core/deps.py`**: `_access_validation_secret()` helper removed; `_access_validator`
  construction reduced to `build_access_validator(settings, _hooks)`.
- **`auth_user_service/core/config.py`**: `TOKEN_ISSUER` / `TOKEN_AUDIENCE` fields removed — they
  are now inherited from `CommonSettings`.
- **`examples/fastapi_service/core/config.py`**: same — duplicate `TOKEN_ISSUER` / `TOKEN_AUDIENCE`
  and unused `Optional` import removed.
- **All env files** updated with `TOKEN_MODE="stateful"` (active) and commented
  `#TOKEN_ISSUER` / `#TOKEN_AUDIENCE` hints for opt-in claim enforcement:
  - `auth_user_service/.env`
  - `examples/fastapi_service/.env`
  - `examples/fastapi_service/.example_env`
  - `examples/docker_compose/stateful_m8/example.env.txt`
  - `examples/docker_compose/local_mysql_m8/example.env.txt`
  - `examples/docker_compose/dev_postgres_m8/.env`
- **`tests/core/deps_test.py`**: `TestAccessValidationSecret` class removed (tested a private helper
  that no longer exists after the refactor).

### Breaking (auth-sdk-m8 consumer services)

- `auth-sdk-m8` bumped to `v0.4.2`.  Reinstall with `pip install -e .` (local) or update the wheel
  reference in consuming services before deploying.

- **Timing-attack prevention on login** (`services/auth.py`): a module-level `_DUMMY_HASH`
  constant (bcrypt of a random secret) is always passed to `verify_password` when the email is
  not found.  Response time is now constant (~185 ms) regardless of whether the user exists,
  eliminating the timing oracle that previously allowed valid-email enumeration.
- **Redis key namespace pollution fix** (`core/client.py` — `LoginRateLimiter._key`): raw user-
  supplied email was used verbatim as a Redis key suffix.  Non-printable characters (CRLF, NUL)
  are now stripped and keys are capped at 255 characters to prevent namespace injection and
  memory exhaustion attacks.
- **HTTPException swallowing in route handlers** (`routes/profile.py`, `routes/sessions.py`,
  `routes/users.py`): broad `except Exception` clauses were silently converting `HTTPException`
  (404, 403, 409) into 500 responses via `BaseController.handle_exception`.  All routes now
  re-raise `HTTPException` before delegating to the exception helper.
- **Profile mutation endpoints crashed on `CurrentUser` type** (`routes/profile.py`): `CurrentUser`
  resolves to the Pydantic `UserModel` from the SDK, not the SQLAlchemy `User` ORM model.
  Calling `.sqlmodel_update()` or `session.add(current_user)` on a Pydantic object raised
  `AttributeError` → 500 on every write.  All mutation routes now fetch `db_user = session.get(User,
  current_user.id)` before any write.
- **Dead SQLModel query in sessions route** (`routes/sessions.py`): `statement.where(...)` returns
  a new object — the result was discarded, so `get_session_by_user` returned all sessions instead
  of filtering by user.  Dead code removed; the route already carries the
  `get_current_active_superuser` dependency so no functional restriction was bypassed.
- **Logout always returned 401** (`routes/login.py`): `SecurityHelper.get_refresh_token_from_cookie`
  was used directly as `Depends()`.  FastAPI treated its unannotated `str` parameter as a query
  param, never reading the cookie.  Fixed with a `_get_refresh_cookie` wrapper annotated with
  `Cookie(None, alias="refresh_token")`.

### Added

- **`GET /health/` endpoint** (`routes/health.py`): reports operational status without requiring
  authentication.  Response fields: `status` (`ok` | `degraded`), `token_mode`, `effective_mode`
  (`stateless_degraded` when Redis is unreachable in `stateful`/`hybrid` mode), `redis`,
  `database`, `revocation_available`, `rate_limiting_available`.
- **`handle_route_exception()` helper** (`core/exceptions.py`): unified exception mapper used by
  all route handlers.  Maps `OperationalError` → 503 (database unreachable), `RedisConnectionError`
  → 503 (cache unreachable), re-raises `HTTPException`, delegates everything else to
  `BaseController.handle_exception` (500).
- **Global exception handlers in `main.py`**: `SQLAlchemyOperationalError` and
  `RedisConnectionError` are caught at the application level and return a structured 503 JSON
  response — a backstop for any infra error that escapes a route's own `try/except`.
- **Lifespan startup check** (`main.py`): at startup, the service logs `CRITICAL` when Redis is
  unreachable but `TOKEN_MODE` requires it, and `CRITICAL` when the database is unreachable.
  This makes misconfigured or partially-started stacks immediately visible in container logs.
- **Prometheus observability** via `auth_sdk_m8.observability` (SDK `[observability]` extra):
  - `auth_user_service` exposes `GET /user/metrics` when `METRICS_ENABLED=true`.  Auth-specific
    counters (`login_attempts_total`, `token_refresh_total`, `logout_total`,
    `token_validation_failures_total`, `oauth_attempts_total`) are incremented in route handlers
    and `get_current_user`.
  - `examples/fastapi_service` exposes `GET /fastapi/metrics`.  HTTP groups only (`traffic`,
    `performance`, `reliability`, `health`) — no auth counters.
  - Both services inherit `METRICS_ENABLED` and `METRICS_GROUPS` from
    `ObservabilitySettingsMixin` (MRO-safe multiple inheritance).
  - Zero overhead when disabled: no middleware registered, no counters allocated, `get()` returns
    `None` so all call sites short-circuit in O(1).
  - `examples/docker_compose/stateful_m8/prometheus/prometheus.yml` updated with correct
    `metrics_path` for each service (`/user/metrics` and `/fastapi/metrics`).
- **`TOKEN_MODE` configuration** (`stateless` | `hybrid` | `stateful`): controls whether Redis
  is required at startup, whether JTI blacklist checks run per-request, and whether DB sessions
  are persisted on login.  Defaults to `stateful` for backward compatibility.
- **Per-algorithm token signing keys**: `ACCESS_TOKEN_ALGORITHM` and `REFRESH_TOKEN_ALGORITHM`
  replace the single ambiguous `TOKEN_ALGORITHM` (backward-compat alias preserved via SDK
  validator).
- **Asymmetric signing (RS256 / ES256)**: `ACCESS_PRIVATE_KEY` (PEM, auth service only) and
  `ACCESS_PUBLIC_KEY` (PEM, distributed to all consumers) are new optional env vars.
  `ACCESS_SECRET_KEY` is now required only for HS256; RS256/ES256 deployments leave it blank.
- **`RedisRefreshStore`** (`auth_user_service/core/client.py`): allowlist-backed refresh token
  store.  Each active refresh JTI is registered as a Redis key with a matching TTL; rotation is
  atomic via a Redis pipeline.  Replaces the old blacklist approach — an absent key means
  unknown/revoked, which is safe-fail when Redis is flushed.
- **`examples/docker_compose/dev_postgres_m8/`**: new Compose stack using `postgres:16-alpine`
  with Traefik, Redis, auth service, and example service; includes full env files with inline
  comments for asymmetric key configuration.
- **Observability hooks**: `_LoggingHooks` attached to `TokenValidator` in both
  `auth_user_service/core/deps.py` and `examples/fastapi_service/core/deps.py`.  Successful and
  failed validations emit `DEBUG` / `WARNING` log lines with `jti`, `sub`, and failure reason.

### Changed

- **`get_redis_client()`** (`core/deps.py`): now issues a `ping()` before returning the client.
  Returns `None` when the server is unreachable so all `if redis is not None:` guards in routes
  correctly reflect actual connectivity — previously the pool object was always returned,
  making guards useless when Redis was down.
- **Google OAuth PKCE** (`services/auth.py`, `routes/google_auth.py`): both `get_google_login_url`
  and the callback route now explicitly check that Redis is available before touching `PKCEStore`.
  A missing Redis connection raises `HTTPException(503)` with a clear message instead of
  crashing with 500 or returning a misleading "Invalid state parameter" (400).
- **`auth_user_service/core/deps.py`**: Redis connection pool is only created when
  `TOKEN_MODE != "stateless"`.  JTI blacklist check is only performed when
  `TOKEN_MODE == "stateful"`.  `get_current_user` no longer accepts a `redis` dependency
  argument — it calls `get_redis_client()` internally when needed.
- **`auth_user_service/routes/login.py`**: login registers the refresh JTI in
  `RedisRefreshStore`; token refresh validates via allowlist and atomically rotates to the new
  JTI; logout revokes the refresh JTI and (stateful mode) blacklists the access JTI.  Rate
  limiting and DB session creation are gated on Redis availability and `TOKEN_MODE`.
- **`examples/fastapi_service/core/deps.py`**: `TokenValidator` is now a module-level singleton
  (was re-created per-request); `_access_validation_secret()` selects the public key for
  RS256/ES256 automatically.
- **`examples/docker_compose/local_mysql_m8/auth.env`**: `SECRET_KEY` commented out;
  `ACCESS_TOKEN_ALGORITHM`, `REFRESH_TOKEN_ALGORITHM`, `TOKEN_MODE`, and `GOOGLE_CLIENT_*`
  added; asymmetric key generation instructions added as comments.
- **`examples/docker_compose/local_mysql_m8/docker-compose.yml`**: `SECRET_KEY` removed from
  service env blocks; `ACCESS_PRIVATE_KEY`, `ACCESS_PUBLIC_KEY`, and all new token vars
  forwarded with `${VAR:-default}` fallbacks.

### Breaking

- Existing refresh sessions are invalidated on first deploy — JTIs are not pre-populated in the
  new Redis allowlist and will be rejected on the next refresh attempt.  Users must re-login once
  after upgrading.

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
