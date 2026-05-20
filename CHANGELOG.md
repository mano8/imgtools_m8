# Changelog

All notable changes to `fa-auth-m8` will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **mkcert-based TLS for local development** — `init-certs.sh` now detects `mkcert` and uses it to generate locally-trusted certificates, eliminating `ERR_CERT_AUTHORITY_INVALID` browser errors and silent Chrome extension `fetch()` failures. Falls back to an OpenSSL self-signed cert with a clear install prompt when `mkcert` is absent. All `dynamic_conf.yml` files updated to load `local.crt` / `local.key` (the generated output) instead of the committed placeholder `m8_app_crt.pem` / `m8_app_key.pem`.

- **`/user/health` and `/user/metrics` restricted to internal entryPoint** — these routes are no longer reachable via the public `websecure` entryPoint (port 443/4430). They remain accessible on the localhost-bound `api` entryPoint (port 9000) so Prometheus scraping and Docker-internal health probes are unaffected. Public auth routes now use `auth-public-router` (websecure, excludes health/metrics); internal routes use `auth-internal-router` (api, `internal-only` IP-allowlist middleware). Same split applied to `fastapi_service`.

- **Traefik log level corrected** — `log.level` was set to `WARNING` (Python convention) instead of Traefik's `WARN`, causing Traefik to log `Unknown Level String: 'warning'` and crash-loop on startup. Fixed in all 10 `traefik.yml` files.

- **Traefik: `http3` removed from `api` entryPoint** — QUIC is UDP-based; the `api` entryPoint at port 9000 handles TCP-only service-to-service traffic. The `http3: {}` directive there was a no-op misconfiguration. HTTP/3 is retained on `websecure` only. UDP port `4430/udp` is now explicitly mapped in all `docker-compose.yml` files so QUIC actually works on the public HTTPS entryPoint.

- **Docker Compose service labels simplified** — `auth_user_service` and `fastapi_service` Traefik labels reduced to `traefik.enable=true`. All routing rules are now exclusively defined in `dynamic_conf.yml` (file provider), eliminating the implicit docker-provider router that competed with the file-provider router on both entryPoints.

- **Dead `acme.json` mount removed** — `lite_mysql_m8/docker-compose.yml` mounted `./traefik/acme.json` with no configured `certificatesResolvers`. Mount removed.

- **`cert-init` one-shot service added to all 10 compose stacks** — a Docker-native Alpine container generates `local.crt`/`local.key` inside the bind-mounted `traefik/certs/` directory on the first `docker compose up`, removing all host-side prerequisites (no bash, no openssl, no mkcert required to get HTTPS working). The `traefik` service depends on it via `condition: service_completed_successfully`; subsequent runs skip cert generation instantly when the files already exist. The host-side `init.sh --rotate-certs` (mkcert) path remains the upgrade route to browser-trusted certificates.

### Documentation

- **`traefik/certs/README_DEV.md` rewritten for all 10 example stacks** — replaces the stale raw-openssl command snippets with: a port reference table (4430=HTTPS, 9000=HTTP-only, 8080=dashboard), a browser compatibility table (Chrome/Edge/Brave/Opera/Vivaldi/Safari trusted automatically with mkcert; Firefox requires manual NSS import), mkcert install instructions per OS, a step-by-step Firefox CA import walkthrough, and mkcert cleanup instructions. Explains why Firefox trust-store automation was intentionally not scripted (trust expansion concern).

- **`README.md` Quick Start updated** — added a "Browser TLS compatibility" table under the mkcert install step, and a pointer to `traefik/certs/README_DEV.md` for the Firefox manual import walkthrough.

### Security

- **Refresh key rotation support** — `REFRESH_SECRET_KEY_OLD` env var (optional, default unset). When configured, refresh tokens that fail validation against the current `REFRESH_SECRET_KEY` are automatically retried against the old key, providing a zero-downtime rotation window. Expired tokens are never retried. A `WARNING` is logged each time the old key is used. Remove the var once all pre-rotation refresh tokens have expired (after `REFRESH_TOKEN_EXPIRE_MINUTES`). Implemented in auth-sdk-m8 `SecurityHelper.decode_refresh_token` and `RefreshTokenPolicy`; wired in `routes/login.py` for both the refresh and logout decode paths.

- **`RefreshRateLimiter` on `/login/refresh-token/`** — fixed-window limiter keyed by `user_id` (10 rotations / 5 min). Closes the C2 session integrity denial path: an attacker holding a captured refresh token could previously spam rotations at zero cost to continuously trigger `revoke_all_user_sessions` against the victim, forcing indefinite re-authentication. Implemented in `core/client.py`; wired in `routes/login.py` immediately after token decode, before the allowlist check.

- **Configurable login and refresh rate limits** — `LoginRateLimiter` and `RefreshRateLimiter` limits are now operator-controlled via `CommonSettings` (auth-sdk-m8) instead of compile-time constants. Four new env vars with Pydantic bounds (`ge=1`):
  - `LOGIN_RATE_LIMIT_REQUESTS` (default `5`, max `1000`) — max login attempts per window
  - `LOGIN_RATE_LIMIT_WINDOW_MINUTES` (default `15`, max `1440`) — brute-force window
  - `REFRESH_RATE_LIMIT_REQUESTS` (default `10`, max `1000`) — max refresh rotations per window
  - `REFRESH_RATE_LIMIT_WINDOW_MINUTES` (default `5`, max `1440`) — churn-prevention window
  Startup logs the active limits with computed effective rates (req/min) for each control. `config_health.py` warns at startup if the effective rate exceeds per-control thresholds (login > 5 req/min, refresh > 20 req/min) indicating a highly permissive configuration that may weaken abuse protection. All 10 `auth.env.example` files include the new vars as commented defaults.

- **Configurable per-control auth degradation policy** — five new settings in `CommonSettings` (auth-sdk-m8) define the service posture when Redis is unavailable for each security control:
  - `AUTH_STRICT_MODE` (default `false`) — global override forcing all controls to `fail_closed`
  - `REFRESH_VALIDATION_FAILURE_MODE` (default `fail_closed`) — refresh allowlist unavailable: reject with 503 rather than silently allowing rotation without JTI validation. Removes C1's primary enabling condition (persistent access after silent logout failure)
  - `SESSION_WRITE_FAILURE_MODE` (default `fail_closed`) — revocation failure on logout: return 503 so the client knows the session was not fully revoked, rather than silently returning success
  - `RATE_LIMIT_FAILURE_MODE` (default `fail_open`) — skip rate limit checks when Redis is down; availability tradeoff
  - `ACCESS_REVOCATION_FAILURE_MODE` (default `fail_open`) — skip access token blacklist read when Redis is down; short TTL bounds the exposure window

- **`SameSite=Strict` on refresh-token cookie** — upgraded from `SameSite=Lax`. The auth service has no legitimate cross-site POST use case, so `Strict` provides the maximum CSRF protection at no functional cost.
- **`REFRESH_TOKEN_ALGORITHM` startup enforcement** — `CommonSettings._sync_token_algorithms` now raises `ValueError` at startup if `REFRESH_TOKEN_ALGORITHM` is configured to anything other than `HS256`. Refresh tokens are internal-only and must use symmetric signing; this converts a silent misconfiguration trap into a hard startup failure.
- **`SecurityHelper.verify_password` exception narrowed** — `except Exception` tightened to `except ValueError`; removed the dead `# return pwd_context.verify(...)` comment. Previously, bcrypt internal errors (malformed stored hash, memory fault) silently returned `False` with no log or metric, masking legitimate failures and reducing anomaly-detection sensitivity.

### Added

- **`auth_revocation_failure_total` Prometheus counter** (auth metrics group) — tracks token revocation failures per operation (`operation: access_blacklist | refresh_allowlist | db_session`). Emitted on every caught exception in the logout revocation path. Previously these failures were silent; they now surface in Prometheus and alert rules can be built against them.

- **`auth_degraded_decision_total` Prometheus counter** (auth metrics group) — emitted on every degraded-mode decision, i.e. each time a Redis-dependent control is consulted while Redis is unavailable. Labels: `control` (`rate_limit | refresh_validation | session_write | access_revocation`), `mode` (`fail_open | fail_closed`), `reason` (`redis_unavailable | revocation_failed`). Allows building Prometheus alerts on degraded-mode frequency and mode distribution before HTTP 503s appear in error rates.

- **`auth_redis_circuit_breaker_open` Prometheus gauge** (auth metrics group) — set to `1` when the Redis circuit breaker is open (Redis unavailable, requests short-circuited) and `0` when closed (Redis healthy). Updated on every successful or failed ping in `get_redis_client()`.

- **`auth_degradation_mode_active` Prometheus gauge** (auth metrics group) — set at startup from `CommonSettings` for each security control. Labels: `control`, `mode`. Value is always `1` for the active configured mode. Allows alert rules like `auth_degradation_mode_active{control="rate_limit", mode="fail_open"} == 1 and auth_redis_circuit_breaker_open == 1` to page on unprotected degraded paths.

- **`auth_session_integrity_denial_total` Prometheus counter** (auth metrics group) — incremented whenever the Lua rotation script detects a consumed JTI (token reuse attack). Label: `trigger=reuse_detected`. Paired with `logger.critical` emission and immediate `revoke_all_user_sessions` chain invalidation, giving a Prometheus alert surface for any reuse event.

- **`REDIS_SSL` connection pool TLS** — `ConnectionPool` now passes `ssl=settings.REDIS_SSL`. Defaults to `False`; set `REDIS_SSL=true` for Redis over TLS in staging/production. All 10 `auth.env.example` files include the option as a commented default.

- **redis-py 7.x compatibility fix** — `ConnectionPool` construction now uses `**({"ssl": True} if settings.REDIS_SSL else {})` instead of `ssl=settings.REDIS_SSL`. redis-py 7.4.0 raises `TypeError` when `ssl=False` is forwarded to `AbstractConnection.__init__()`, which caused the circuit breaker to open silently at startup even with Redis healthy. The exception handler in `get_redis_client()` now logs the exception message (`error=%s`) so connection failures are diagnosable without container exec.

- **`require_redis` live test marker** — new pytest marker that auto-skips tests requiring Redis when the running stack reports `redis=unavailable` in its health response. `conftest.py` extended: `_detect_stack()` now captures `redis_ok` from the `/health/` body; `pytest_collection_modifyitems` skips `require_redis`-marked tests and all `live_stateful` / `live_hybrid` tests when Redis is unavailable. Prevents false failures from rate-limit and JTI-store tests when Redis is down.

- **Unit tests for `REFRESH_SECRET_KEY_OLD` key-rotation fallback** (`tests/security/test_refresh_key_rotation.py`) — five tests covering `SecurityHelper.decode_refresh_token` with `old_secrets`: current-key token accepted without `old_secrets`; old-key token accepted when `old_secrets` is set; old-key token rejected when `old_secrets` is absent; expired old-key token rejected regardless; unknown-key token rejected regardless. Closes the test gap on the zero-downtime rotation path introduced in this release.

- **Degradation contract documented** — `README.md` Infrastructure Resilience section now explicitly documents the two stable states (Redis healthy / Redis fully down), the transient inconsistency regime, and why the asymmetric fail-open/fail-closed posture is intentional. Includes observable signals (`auth_redis_circuit_breaker_open`, `auth_degraded_decision_total`, `/health/` `circuit_breaker` field).

- **`/health` circuit breaker and degradation mode fields** — health endpoint now includes `circuit_breaker` (`"open"` | `"closed"`) and `degradation_modes` object showing the effective mode per control. Operators can see the degradation posture without scraping Prometheus.

- **Revocation failure log level upgraded** — all three logout revocation failures (`access_blacklist`, `refresh_allowlist`, `db_session`) now emit `ERROR` instead of `WARNING`, producing a structured log event that incident-response tooling can page on.

- **`vault_rs256_postgres_m8` production Vault examples** — three new files for deploying with an external Vault:
  - `.env.prod_example` — `.env` with `AUTH_DB_PASSWORD`, `REDIS_PASSWORD`, and `VAULT_DEV_TOKEN` removed; shows what CI/CD injects at deploy time.
  - `auth.env.prod_example` — `auth.env` with `ENVIRONMENT=production`, API docs disabled, and no DB/Redis passwords; documents injection via Docker secrets.
  - `vault/docker-compose.vault.yml` + `vault/config/vault.hcl` — standalone Vault compose in server mode (persistent file storage) for local integration testing without dev mode.
  - README section "Using with an external Vault" covering option A (separate local Vault compose), option B (managed Vault), the prod example files, and how to extend Vault coverage to additional secrets.

- **README overhaul across all 10 Docker Compose stacks** — every stack README rewritten or substantially extended:
  - Root `README.md`: stack table expanded to all 10 stacks, Quick Start updated, architecture diagram fixed.
  - `examples/docker_compose/README.md`: complete rewrite with decision guide, algorithm and token mode comparison tables, live test commands for each stack.
  - `lite_mysql_m8`, `lite_postgres_m8`: fixed stale titles (`local_mysql_m8`, `dev_postgres_m8`), added Architecture, Limitations, and Live testing sections.
  - `lite_rs256_m8`: removed phantom monitoring sections, corrected Limitations.
  - `lite_es256_m8`, `lite_hybrid_m8`, `lite_stateless_m8`: written from scratch with correct algorithm/mode settings, explicit warnings about env example defaults, Redis-usage tables.
  - `stateful_m8`: added Summary nav, Architecture diagram, Live testing section.
  - `env_rs256_m8`: new README distinguishing this stack from `vault_rs256_postgres_m8` (env-file secrets vs Vault).
  - `vault_rs256_postgres_m8`: added "not production-ready as-is" disclaimer, plaintext-exposure table, bundled-vs-separate Vault comparison, and the new external-Vault section.
  - `template`: updated stack comparison table to list all 10 stacks with correct names.
  - All READMEs have a Summary with in-page links and a nav footer.

- **`RS256_m8` directory renamed to `env_rs256_m8`** — clarifies that this stack uses plain env files, distinguishing it from `vault_rs256_postgres_m8` which uses HashiCorp Vault.

- **`vault_rs256_postgres_m8` compose stack** — new production-grade example combining PostgreSQL 16, RS256 asymmetric signing, HashiCorp Vault secret injection, and Prometheus/Grafana observability.
  - Vault dev-mode service with a one-shot `vault_init` container that writes `DB_PASSWORD` and `REDIS_PASSWORD` to `secret/data/app`; `auth_user_service` depends on it via `service_completed_successfully`.
  - `SECRET_PROVIDER` and `VAULT_ADDR` moved to the docker-compose `environment` block (not the dotenv file) to avoid pydantic `extra="forbid"` rejection.
  - `hvac>=2.0.0` added to `requirements_prod.txt` so Vault injection is available in Docker builds.
  - Production hardening guide (server mode, scoped app-policy token, Vault agent sidecar) and key-rotation procedure documented in stack README.

### Fixed

- **`SessionController.revoke_session_jti`** (`services/client_sessions.py`) — refactored to accept an optional `redis: Optional[Redis] = None` parameter, consistent with all sibling session methods. Logout now passes the route-scoped client directly instead of calling `get_redis_client()` internally.
- **`user_id` type standardised to `str`** in `SessionController.get_user_active_sessions` and `revoke_all_user_sessions` — JWT `sub` claims are always strings; the previous `uuid.UUID` annotation created a type-system mismatch at every call site.
- **`UserController.get_user` return type** corrected to `Optional[User]` (`services/users.py`) — `.first()` returns `None` when no row is found.
- **`logging.basicConfig()` removed** from `services/client_sessions.py` — library modules must not override the root logger configuration of the host application.
- **`get_tokens_expire()` return type** corrected from `Union[timedelta, timedelta]` to `tuple[timedelta, timedelta]` (`services/auth.py`).
- **`PKCEStore.pop` simplified** — `return result if result is not None else None` → `return result` (`core/client.py`).
- Typo `expiarition` → `expiration` in `AuthController.get_tokens_expire` docstring.
- **`create_auth_tokens` return type** corrected from `Union[str, str, str]` to `tuple[str, str, str]` (`services/auth.py`).
- **`get_user_by_email` return type** corrected from `User` to `Optional[User]` (`services/users.py`) — `.first()` returns `None` when no row is found.
- **`session.exec(delete(...))` type-ignore removed** — replaced with `session.execute()` in `routes/users.py`; `exec()` is the ORM-typed overload for `select`, `execute()` is correct for DML statements.

- **Example env file inconsistencies** — four corrections to `auth.env.example` files that caused misconfigured stacks out-of-the-box:
  - `stateful_m8`: `METRICS_ENABLED=false` → `true` (compose includes Prometheus + Grafana)
  - `lite_stateless_m8`: `TOKEN_MODE=hybrid` → `stateless`
  - `lite_hybrid_m8`: `TOKEN_MODE=stateful` → `hybrid`
  - `lite_es256_m8`: header and `ACCESS_TOKEN_ALGORITHM` corrected from `RS256` → `ES256`

- **`CommonSettings.settings_customise_sources` classmethod** (auth-sdk-m8): pydantic-settings 2.x calls sources with no positional arguments and uses a 5-arg classmethod calling convention (`settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings`). The standalone function passed via `model_config` was silently ignored. Vault injection is now wired as a proper `@classmethod` override on `CommonSettings`, so all subclasses inherit it without any `model_config` entry.
- **Vault source callable signature**: pydantic-settings 2.x calls each source with no arguments (`source()`); the inner `_vault_source` function no longer declares a settings parameter.
- **`auth_user_service/core/config.py`**: removed the `settings_customise_sources=` entry from `SettingsConfigDict` (it was a no-op) and the corresponding import.
- **`tests/live/conftest.py`**: RSA key lookup now searches `vault_rs256_postgres_m8/keys/` first, then falls back to `RS256_m8/` and `lite_rs256_m8/`.

---

## [0.7.1] - 2026-05-17

### Fixed

- **`get_user` by ID**: `users.get_user()` was looking up by email when called with an ID argument; query corrected to use `user_id`. User count query simplified.

### Added

- **Modular live test suite** — monolithic `test_redteam_rs256.py` replaced by six focused modules, each gated by a pytest mark so only relevant tests run against a given stack:
  - `test_security_universal.py` — 13 attack categories (A–M) that apply to any algorithm and token mode.
  - `test_asymmetric.py` — asymmetric-only attacks (alg=none confusion, JWKS exposure, attacker-generated key); auto-skipped when the stack uses HS256.
  - `test_hs256.py` — HS256-specific attacks; auto-skipped on asymmetric stacks.
  - `test_stateful.py` — token-revocation and session-chain guarantees for `TOKEN_MODE=stateful`.
  - `test_hybrid.py` — degraded-mode and partial-Redis behaviour for `TOKEN_MODE=hybrid`.
  - `test_stateless.py` — no-Redis guarantees for `TOKEN_MODE=stateless`.
  - `tests/live/suites/` — shared helpers (`auth_flows.py`, `token_forge.py`) that de-duplicate login flows and JWT forgery fixtures across all modules.
  - `conftest.py` auto-detects the running stack's algorithm and token mode; `require_algorithm` / `require_token_mode` marks trigger automatic skip.
- **New `pytest.ini` markers**: `live_security`, `live_asymmetric`, `live_hs256`, `live_stateful`, `live_hybrid`, `live_stateless`, `require_algorithm`, `require_token_mode`, `destructive`.
- **Session deletion and revocation tests** (`tests/services/client_sessions_test.py`) — covers `delete_session`, `revoke_session`, and Redis JTI cleanup paths.
- **100% branch coverage** across `core/client.py`, `core/deps.py`, and `services/api_keys.py`.

---

## [0.7.0] - 2026-05-16

### Added

- **API key rate limiting** — full fixed-window enforcement across MINUTE, HOUR, DAY, and MONTH periods.
  - Redis `INCR + EXPIRE` in a pipeline (atomic) per window; correct per-period bucket format prevents HOUR/DAY/MONTH counters from resetting every minute.
  - Priority chain: per-key `RateLimit` rows → per-user defaults → `API_KEY_DEFAULT_LIMIT_*` settings.
  - `RateLimitResult` dataclass carries `allowed`, `exceeded_period`, `limit`, `remaining`, `reset_at`.
  - `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` response headers populated from the tightest (MINUTE) window.
  - `Retry-After` header on 429 responses.
  - Degraded-mode support: when Redis is unavailable and `API_KEY_STRICT_RATE_LIMIT=false` (default), requests are allowed through; strict mode returns 503.
- **`get_current_api_key` FastAPI dependency** (`core/deps.py`): validates `X-API-Key` header, enforces rate limits, and queues a write-behind `last_used_at` update to Redis.
- **Write-behind `last_used_at` flush** (`main.py` lifespan): hardened asyncio background task — exception-shielded loop, final flush on graceful shutdown (5 s timeout), Prometheus histogram for flush latency.
- **API key endpoints** under `/user/profile/api-keys/`:
  - `GET /verify` — validate `X-API-Key` header, enforce rate limits, return key metadata (used by consumer services).
  - `POST /` — create key, enforce `API_KEY_MAX_PER_USER` cap, return plaintext once.
  - `GET /` — list all keys for the current user (metadata only; hash never exposed).
  - `GET /{key_id}` — retrieve metadata for a single key.
  - `DELETE /{key_id}` — revoke a key; emits `api_key_lifecycle_total{action="revoked"}`.
- **`Period.MONTH`** added to `auth_sdk_m8.schemas.base.Period` enum.
- **5 new Prometheus metrics** in `auth_sdk_m8.observability.metrics` (auth group):
  - `auth_api_key_validations_total` — result: success | invalid | revoked | expired.
  - `auth_api_key_rate_limit_checks_total` — result: checked | allowed | blocked.
  - `auth_api_key_rate_limit_hits_total` — period: minute | hour | day | month.
  - `auth_api_key_lifecycle_total` — action: created | revoked.
  - `auth_api_key_flush_duration_seconds` — histogram for write-behind flush latency.
- **`RateLimit` DB model redesigned**: `api_key_id` (nullable FK → `auth_api_key.id`, CASCADE) added as primary enforcement axis; `user_id` made nullable (fallback default); `period` enum extended with MONTH; two UNIQUE constraints (`uq_ratelimit_api_key_period`, `uq_ratelimit_user_period`) and a CHECK constraint (`ck_ratelimit_has_owner`) added.
- **`ApiKey.id`** migrated from VARCHAR to `Uuid` for type consistency with `user.id`.
- **Alembic migration** `99540139637b_api_key_rate_limit_redesign` for all five compose examples.
- **`API_KEY_*` settings** in `auth_user_service/core/config.py`:
  - `API_KEY_STRICT_RATE_LIMIT` (default `false`), `API_KEY_DEFAULT_LIMIT_MINUTE/HOUR/DAY/MONTH`, `API_KEY_MAX_PER_USER`.
- **Prometheus alert rules** (`prometheus/alerts.yml`) for all three Prometheus-enabled compose stacks:
  - `ApiKeyBlockRatioHigh` — hits/checks > 10% over 5 min.
  - `ApiKeyRateLimitInvariantViolation` — hits > checks × 1.1 (instrumentation sanity guard).
  - `ApiKeyFlushLatencyHigh` — p99 flush > 500 ms.
  - `ApiKeyHighInvalidRate` — > 1 invalid/revoked/expired key/s over 5 min.

### Fixed

- **`RedisRateLimiter` bucket format bug**: HOUR, DAY, and MONTH periods were using the same `%Y%m%d%H%M` format as MINUTE, creating a new Redis key every minute instead of accumulating in a single window. Each period now has a distinct bucket format.
- **INCR + EXPIRE race condition**: the two Redis calls are now issued in a single pipeline, preventing a key with no TTL if the service crashes between them.

### Changed

- `RedisRateLimiter` public API: `increment()` replaced by `check_and_increment()` (returns `RateLimitResult`) and `check_all_limits()`. Internal `_increment()` handles the pipelined atomic counter.

---

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
