# Changelog

All notable changes to `fa-auth-m8` will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [0.11.0] — 2026-05-26 · Redis isolation — consumer services use HTTP introspection

### Breaking changes

- **Consumer services no longer connect to auth Redis directly.** The `REDIS_*`
  env vars (`REDIS_HOST`, `REDIS_PORT`, `REDIS_USER`, `REDIS_PASSWORD`) are
  **removed from `fastapi_service` and all `api.env` / `api.env.example`
  files**.  Consumer services that set these fields must remove them; the
  `auth-sdk-m8` SDK now rejects unknown Redis fields for consumer roles via
  `extra="forbid"`.

- **`INTROSPECTION_URL` and `PRIVATE_API_SECRET` are now required when
  `AUTH_SERVICE_ROLE=consumer` and `TOKEN_MODE=stateful`.**  Both must be set
  in each consumer's env file before upgrading a stateful stack.
  `PRIVATE_API_SECRET` must match the auth service value.

### Added

- **`POST /private/v1/jti-status`** — new private inter-service endpoint on
  `auth_user_service`.  Accepts `{"jti": "..."}` and returns
  `{"active": bool}`.  Hidden from Swagger (`include_in_schema=False`).
  Protected by `X-Internal-Token` + Docker network isolation like all private
  routes.  Fails-open when Redis is unavailable (matches the default
  `ACCESS_REVOCATION_FAILURE_MODE` behaviour).

- **`examples/fastapi_service/core/revocation.py`** — `RemoteRevocationClient`
  async HTTP client (httpx-backed).  Fail-open by default; set
  `fail_closed=True` to reject tokens when the auth service is unreachable.

- **`INTROSPECTION_URL`** (`Optional[HttpUrl]`) and **`PRIVATE_API_SECRET`**
  (`Optional[SecretStr]`) added to `fastapi_service` `Settings`.  Validated at
  startup: both required for `consumer + stateful`; ignored for `hybrid` /
  `stateless`.

### Changed

- `fastapi_service/core/deps.py` — removed Redis pool, `get_redis_client`,
  and `RedisDep`.  `get_current_user` is now `async`; revocation check calls
  `RemoteRevocationClient.is_revoked()` instead of `AccessTokenBlacklist`.
  Returns HTTP 503 in fail-closed mode when the introspection endpoint is
  unreachable.

- `fastapi_service/main.py` — startup check updated: logs introspection URL
  instead of Redis connectivity.  Lifespan now closes the revocation client
  httpx session on shutdown.

- All six `docker-compose.yml` stacks — removed `redis_cache: condition:
  service_healthy` from `fastapi_service.depends_on`.  The consumer no longer
  needs Redis to start; it waits only for the database and auth service.

- All six `api.env` and `api.env.example` files — removed `REDIS_*` block;
  added `INTROSPECTION_URL` + `PRIVATE_API_SECRET` for stateful stacks;
  hybrid (`rs256_m8`) shows them commented-out as optional.

---

## [0.10.0] — 2026-05-23 · Remove avatar upload; clean shared settings; unify secret-key validation

### Breaking changes

- **`POST /profile/upload_avatar/` removed.** The auth service no longer stores or serves
  avatar files. The `avatar` field on user profiles now accepts only `http://` or `https://`
  URLs. Any existing row whose `avatar` column contains a bare filename (e.g.
  `"abc123.jpg"`) will fail Pydantic validation at the schema layer — update those rows to
  a full URL before migrating to this version.

- **`STATIC_BASE_PATH` and `TEMPLATES_BASE_PATH` removed from `CommonSettings`** (and from
  all env example files). These settings had no business being in the shared backend base
  class. Services that referenced them will fail at startup — remove the keys from your
  `.env` files.

### Changed

- Avatar field description updated to "HTTP/HTTPS URL to user avatar image". The
  `UserBase` model now validates the URL at the Pydantic layer (rejects non-http/https
  schemes, whitespace, protocol-only strings, and missing hosts).

- `SECRET_KEY_REGEX` in `auth-sdk-m8` unified with `PASSWORD_REGEX`: both now require
  upper, lower, digit, and at least one non-alphanumeric character, with no whitespace.
  Previously restricted to `[A-Za-z0-9_-]`; now accepts any non-alphanumeric special
  character (`[^a-zA-Z0-9]`). Minimum length unchanged at 32 characters.

- All env example `auth.env.example` generator comments updated to use
  `secrets.token_urlsafe(48)` (simpler, standards-aligned).

### Removed

- `auth_user_service/utils/files.py` (`FilesHelper`) — deleted.
- `ResponseUploadedAvatar` schema — deleted.
- `STATIC_BASE_PATH` static-mount block from `auth_user_service/main.py`.
- `STATIC_BASE_PATH` / `TEMPLATES_BASE_PATH` from all env example and live `.env` files.
- Unused `get_templates()` helper and static mount from `examples/fastapi_service`.
- Static volume mounts (`./auth_user/static`, `./fastapi_service/static`, `auth_static`) from
  all six Docker Compose example stacks; `auth_static` named volume removed from `hardened_m8`.
- Empty `auth_user/` and `fastapi_service/` placeholder directories from all six stacks.

### Fixed

- Redis `redis-cli -a` password flag replaced with `REDISCLI_AUTH` env var across all six
  stacks — eliminates the "Using a password with '-a' option on the command line interface
  may not be safe" warning on startup and in healthchecks.

---

## [0.9.0] — 2026-05-22 · Example stack consolidation (10 → 6) + Docker Hub image + hardened stack

### Changed

- **Docker Compose examples consolidated from 10 stacks to 5** — each new stack serves
  a distinct audience with a clear "choose this when" decision:
  - `quickstart_m8` — replaces `lite_mysql_m8` + `template`; HS256, stateful, MariaDB;
    recommended starting point. Token mode changed from `hybrid` to `stateful` for
    consistency with the other HS256 stacks. Stateless mode remains available via a
    commented `TOKEN_MODE=stateless` line in `auth.env.example`.
  - `postgres_m8` — replaces `lite_postgres_m8`; HS256, stateful, PostgreSQL 16; no change
    to config, pure rename.
  - `rs256_m8` — replaces `lite_rs256_m8`, `lite_es256_m8`, `env_rs256_m8`,
    `lite_hybrid_m8`; RS256 asymmetric signing, hybrid mode, MariaDB; no monitoring
    services.
  - `metrics_m8` — replaces `stateful_m8`; HS256, stateful; database migrated from MariaDB
    to PostgreSQL 16; Prometheus + Grafana retained.
  - `hardened_m8` — new stack; PostgreSQL 16, RS256, stateful, Prometheus + Grafana;
    container hardening (`no-new-privileges`, `cap_drop: ALL`, `read_only`, tmpfs),
    network segmentation (`app_net` / `data_net internal`), `AUTH_STRICT_MODE=true`,
    `fail_closed` degradation policy. `auth_user_service` from Docker Hub image.
  - `vault_m8` — renamed from `vault_rs256_postgres_m8`; `auth_user_service` now pulls
    `tepochtli/fa-auth-m8:latest` from Docker Hub instead of building locally. Pin to a
    specific release tag for production use.

- **`vault_m8` env corrections** — `api.env` / `api.env.example` aligned across all stacks:
  `quickstart_m8` `TOKEN_MODE` corrected to `stateful`; `rs256_m8` `TOKEN_MODE` corrected
  to `hybrid` and `METRICS_ENABLED` corrected to `false`; `metrics_m8` `SELECTED_DB` and
  `DB_PORT` corrected to PostgreSQL values.

### Removed

- `lite_es256_m8`, `lite_hybrid_m8`, `lite_stateless_m8`, `env_rs256_m8`, `template` —
  functionality absorbed into the five consolidated stacks above.

### Fixed

- `auth_user_service/scripts/docker_start.sh` and `examples/fastapi_service/scripts/docker_start.sh`
  had Windows CRLF line endings. Volume mounts bypass the Dockerfile's CRLF-strip step,
  causing `exec: no such file or directory` on Linux. Both files converted to LF. Root-level
  `.gitattributes` added enforcing `*.sh text eol=lf` across the repo.

### Documentation

- Each stack now has a self-contained `README.md` with "choose this when" guidance,
  token-mode explanation, and full port/config reference.
- Root `README.md` and `examples/docker_compose/README.md` selection tables updated to
  reflect the five-stack structure.

---

## [0.8.2] — 2026-05-22 · Chrome extension auth template

### Added

- **`examples/addon` — Chrome extension auth template**: fully rewritten from a
  project-specific copy into a minimal, reusable, security-reviewed template.
  Supports three auth flows (Google OAuth, email/password, API keys) against any
  `fa-auth-m8` backend instance.

- **`GET /google-api/login-url/`** (`routes/oauth_login.py`): pure JSON endpoint
  replacing the old Jinja2-backed `/google-api/login/` HTML page.  Accepts
  `redirect_target` + `code_challenge` (extension PKCE), validates URI scheme
  against `OAUTH_ALLOWED_REDIRECT_SCHEMES`, stores a unified
  `OAuthSessionStore` session, and returns the Google OAuth URL.  Hard-rejects
  `http://` and `https://` schemes regardless of configuration.

- **`POST /google-api/exchange/`** (`routes/oauth_login.py`): one-time auth
  code exchange endpoint.  Atomically pops the code from Redis (`GETDEL`),
  verifies the extension PKCE `code_verifier` against the stored
  `code_challenge` using `hmac.compare_digest`, and returns tokens.
  Rate-limited to 10 requests/minute per client IP to prevent Redis
  amplification.

- **`ExchangeRateLimiter`** (`core/client.py`): fixed-window rate limiter keyed
  by client IP for the `/exchange/` endpoint (10 req/60 s window).

- **`CORS_ALLOWED_ORIGIN_SCHEMES` support** (`main.py`): `_build_cors_origin_regex`
  builds a `CORSMiddleware`-compatible `allow_origin_regex` from the new SDK
  setting, enabling scheme-level CORS for Chrome extensions.  Chrome extension
  IDs are constrained to exactly 32 lowercase letters — fails fast at startup
  for unsupported schemes.

- **`GOOGLE_OAUTH_REDIRECT_URI`** (`core/config.py`): explicit fixed callback
  URI for the Google OAuth callback.  Never auto-generated from the HTTP
  request host to prevent host-spoofing.

- **New OAuth settings documented in all 10 `auth.env.example` files**:
  `GOOGLE_OAUTH_REDIRECT_URI`, `OAUTH_ALLOWED_REDIRECT_SCHEMES`,
  `OAUTH_ALLOWED_REDIRECT_PREFIXES`, `CORS_ALLOWED_ORIGIN_SCHEMES`.

### Changed

- **`routes/google_auth.py`** — callback rewritten to use unified
  `OAuthSessionStore.get()+delete()` pattern (not `GETDEL`), deliver
  `auth_code` via URL fragment (`#auth_code=`), and accept client-supplied
  `redirect_target` from the session payload.  Fixed `max_age` cookie bug
  (`timedelta.seconds` → `int(timedelta.total_seconds())`).

- **`core/client.py`** — `PKCEStore` replaced by `OAuthSessionStore` (unified
  session store with `get()+delete()` semantics, 10-min TTL) and `AuthCodeStore`
  (GETDEL single-use, 60 s TTL).  `ExchangeRateLimiter` added.

- **`services/auth.py`** — `get_google_login_url` now returns
  `tuple[str, str, str]` (OAuth URL, state, PKCE verifier).  Callers assemble
  the `OAuthSessionStore` payload; the method no longer touches Redis directly.

### Tests

- **100% branch coverage** across all modified modules (983 statements, 198
  branches, 0 missing).  488 tests pass.

- **`tests/routes/test_oauth_login.py`** — new test file with full branch
  coverage of the two new `oauth_login.py` endpoints, including PKCE
  validation, scheme rejection, CORS origin checks, Redis unavailability,
  rate-limit paths, and metric emission.

- **`tests/core/client_test.py`** — replaced `TestPKCEStore` with
  `TestOAuthSessionStore`, `TestAuthCodeStore`, and `TestExchangeRateLimiter`
  covering all new store and rate-limiter behaviour.

- **`tests/security/test_oauth_adversarial.py`** — rewritten to use
  `OAuthSessionStore` patches; removed tests that patched deleted symbols.

- **`tests/services/auth_test.py`** and
  **`tests/security/test_redis_resilience.py`** — updated to unpack the new
  `tuple[str, str, str]` return from `get_google_login_url` and remove
  patches for symbols no longer present in `services.auth`.

- **Bandit clean** — `bandit -r auth_user_service/` reports no issues
  (Low: 0, Medium: 0, High: 0).

### Removed

- **`routes/oauth_login.py` (old)** — Jinja2-based `/google-api/login/` and
  `/google-api/login_success/` HTML routes deleted.  Replaced with two clean
  JSON endpoints.  Auth templates (`login.html`, `login_success.html`) are now
  dead files in the deployment; operators can remove them.

---

## [0.8.3] — 2026-05-22 · Code quality — cyclomatic complexity

### Changed

- **`routes/google_auth.py`** — `google_auth_callback` refactored: extracted
  `_inc_oauth_metric`, `_build_auth_code_payload`, and `_perform_oauth_exchange`
  helpers to bring CCN from 14 down to 8 (Lizard limit).

- **`examples/addon/src/oauth-callback.tsx`** — extracted `buildAuthStorage`
  helper to decouple storage-object construction from the exchange flow; removes
  a Lizard JSX-parser confusion with inline `?.`/`??` in `chrome.storage.local.set`.

- **`examples/addon/src/layout/Home.tsx`** — extracted `UserInfo` sub-component
  (avatar + name + email conditionals) to reduce `Home` CCN from 11 to 5.

- **`examples/addon/src/types/shared_types.ts`** — `isValidAuthState` rewritten
  with `.every(Boolean)` array check; replaces a chained `&&`/`||` return (CCN 11)
  with a flat array evaluation (CCN 4) that is also easier to extend.

- **`examples/addon/src/dev/chromePolyfill.ts`** — extracted
  `getLocalStorageValues` helper from `createLocalStorageBackend`; simplified
  `get` method to a one-liner delegate call; removed explicit `: void` return
  type annotation (Lizard's JSX parser misidentifies function boundaries when
  TypeScript-only return-type syntax follows `)`).

### Tests

- 488 tests pass.  100% branch coverage maintained (983 statements, 198 branches).

---

## [0.8.1] — 2026-05-20

### CI / Infrastructure

- **Python 3.11–3.14 CI matrix** — GitHub Actions test job now runs against all four interpreter versions (`3.11`, `3.12`, `3.13`, `3.14`) with `fail-fast: false`, exposing version-specific regressions before they reach production.

- **Bandit security job** — standalone CI job runs `bandit -r auth_user_service examples/fastapi_service --severity-level medium` on every push/PR; report uploaded as a workflow artifact. Enforces grade A (no MEDIUM/HIGH issues) as a gate.

- **`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`** — opt-in env var eliminates Node 20 deprecation warnings across all GitHub Actions workflow runs.

- **`workflow_dispatch` on docker-publish** — enables manual workflow triggers without a release tag; uses a `dev` fallback tag on `workflow_dispatch` runs so the metadata action always produces a non-empty tag list. Build-and-push is skipped on manual runs (`push: false`), preventing accidental publishes.

- **Docker Hub `IMAGE_NAME` corrected** — was using the default (`${{ github.repository }}`) which resolves to `mano8/fa-auth-m8`; now uses `${{ secrets.DOCKERHUB_USERNAME }}/fa-auth-m8` so the image lands in the correct Docker Hub namespace regardless of GitHub org name.

- **`PIP_ROOT_USER_ACTION=ignore`** in Dockerfile builder stage — eliminates the `WARNING: Running pip as the 'root' user` noise line from every Docker build log.

- **Dependabot expanded to pip** — monthly updates for `auth_user_service/requirements_*.txt`, in addition to the existing GitHub Actions SHA updates. The Docker ecosystem entry is omitted because `dhi.io` is not a Dependabot-supported registry; DHI image updates must be applied manually or via digest pinning.

- **Both Dockerfiles upgraded to Python 3.14** — builder and runtime stages both use `python:3.14-slim` (Docker official image, Dependabot-tracked, no registry authentication required). `PIP_ROOT_USER_ACTION=ignore` added to `fastapi_service` builder to match `auth_user_service`.

- **Graceful shutdown fix in both startup scripts** — `docker_start.sh` now uses `exec` before the uvicorn (and debugpy) invocation. Without `exec`, sh is PID 1 and uvicorn never receives `SIGTERM` from `docker stop`, forcing Docker to wait for the stop timeout before sending `SIGKILL`. With `exec`, uvicorn replaces sh as PID 1 and handles the signal directly.

### Added

- **Redis TLS/mTLS cert configuration** (`auth_user_service/core/deps.py`): the Redis `ConnectionPool` now passes `ssl_ca_certs`, `ssl_certfile`, and `ssl_keyfile` when the corresponding settings are provided, enabling CA verification (preventing `CERTIFICATE_VERIFY_FAILED` with self-signed Redis CAs) and optional mTLS client auth. All three kwargs are only forwarded when `REDIS_SSL=true`.

- **`REDIS_SSL_CA`, `REDIS_SSL_CERT`, `REDIS_SSL_KEY` env vars in all 10 `auth.env.example` files**: the three new TLS path fields are documented as commented defaults under `REDIS_SSL`, matching the new `CommonSettings` fields added in `auth-sdk-m8`.

- **Addon env files updated to HTTPS**: `examples/addon/.env.development` and `.env.production` now point to `https://localhost:4430` (matching `.env`) instead of the stale `http://localhost:8000`, ensuring the browser extension's `fetch()` calls go to the correct TLS endpoint.

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
