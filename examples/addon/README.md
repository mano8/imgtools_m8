# Auth-M8 Extension Template

A minimal, secure Chrome extension template that demonstrates all three auth
flows supported by `fa-auth-m8`:

| Flow | Endpoint | Notes |
| --- | --- | --- |
| Google OAuth | `GET /google-api/login-url/` + `POST /google-api/exchange/` | PKCE + one-time code |
| Email / Password | `POST /login/access-token` | JWT decoded for UX only |
| API Key | `GET /profile/api-keys/verify` | Long-lived; see security warning |

---

## Security model

**The extension is a passive bearer-token consumer.** It never validates JWT
signatures — all authorization decisions happen on the backend. JWT payload is
decoded locally *for display only* (name, email, avatar, expiry hint).

- `chrome.storage.local` is **not** a hardened keystore. Stored tokens have
  equivalent sensitivity to a browser session cookie. Do not treat this
  extension as a secure credential vault.
- `expiresAt` is a UX hint for pre-emptive re-login prompts. The authoritative
  signal is a `401` response from the backend.
- Passive JWT rotation (`X-New-JWT`) is intentionally absent — it creates
  concurrent rotation races. Session model: use valid token → `401` → re-login.
- `stateless` `TOKEN_MODE` is **unsuitable** for extension deployments (no
  revocation). Use `stateful` + RS256 or ES256.
- API keys are long-lived credentials. Prefer OAuth or password for interactive
  use.

---

## OAuth architecture

```text
Extension popup                Backend (fa-auth-m8)           Google
─────────────────────────────────────────────────────────────────────
startOAuthLogin()
  generatePKCE()
  store flows[flowId]=verifier
  GET /google-api/login-url/
    ?redirect_target=chrome-extension://{id}/oauth-callback.html?flow_id=X
    &code_challenge=S256_CHALLENGE
                               ──► store OAuthSessionStore{pkce_verifier,
                                        redirect_target, code_challenge}
                               ◄── { url: "https://accounts.google.com/..." }
  chrome.tabs.create({ url })
                                                               [user consents]
                               GET /google-auth/oauth-callback/?code&state
                               ──► OAuthSessionStore.get(state)  [CSRF check]
                               ──► exchange code with Google (backend PKCE)
                               ──► AuthCodeStore.store(auth_code, payload)
                               ──► OAuthSessionStore.delete(state)
                               ◄── 302 chrome-extension://{id}/oauth-callback.html
                                          ?flow_id=X#auth_code=Y
oauth-callback.tsx
  read #auth_code from fragment
  read flows[flowId] verifier
  POST /google-api/exchange/ {code, code_verifier}
                               ──► AuthCodeStore.pop(code)  [GETDEL, atomic]
                               ──► verify S256(code_verifier) == code_challenge
                               ◄── {access_token, expires_at, user:{name,email,avatar}}
  chrome.storage.local.set(auth, user)
  window.close()
                                    [popup detects storage change → re-renders]
```

---

## Quick start

### 1 — Generate keys and start the backend

```bash
cd examples/docker_compose/env_rs256_m8
bash init.sh          # generates RSA keys + mkcert TLS certs
cp auth.env.example auth.env
# edit auth.env: set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_OAUTH_REDIRECT_URI,
#                    OAUTH_ALLOWED_REDIRECT_SCHEMES, CORS_ALLOWED_ORIGIN_SCHEMES
docker compose up
```

Required `auth.env` settings for extension support:

```env
GOOGLE_CLIENT_ID=<your-google-oauth-app-id>
GOOGLE_CLIENT_SECRET=<your-google-oauth-app-secret>
# Must match Google Console redirect URI exactly.
GOOGLE_OAUTH_REDIRECT_URI=https://localhost:4430/user/google-auth/oauth-callback/

# Required for extension fetch() calls (Origin: chrome-extension://{id}).
CORS_ALLOWED_ORIGIN_SCHEMES=chrome-extension://

# URI schemes allowed as redirect_target (default shown).
OAUTH_ALLOWED_REDIRECT_SCHEMES=chrome-extension://

# Metrics (already enabled in env_rs256_m8).
METRICS_ENABLED=true
```

**Google Console:** add `https://localhost:4430/user/google-auth/oauth-callback/`
as an authorised redirect URI for your OAuth app.

### 2 — Build the extension

```bash
cd examples/addon
cp .env.example .env.development   # edit VITE_API_URL if backend URL differs
npm install
npm run build
# output: dist/
```

### 3 — Load in Chrome

1. Open `chrome://extensions` → Developer mode → **Load unpacked** → select `dist/`
2. Copy the Extension ID shown.

No `EXTENSION_ID` config in `auth.env` — `fa-auth-m8` is client-agnostic.

### 4 — Update `manifest.json`

Update `host_permissions` and `connect-src` to match your backend origin:

```json
"host_permissions": ["https://localhost:4430/*"],
"content_security_policy": {
  "extension_pages": "script-src 'self'; object-src 'none'; base-uri 'none'; connect-src 'self' https://localhost:4430;"
}
```

**Both `host_permissions` and `connect-src` must permit the backend host** — they
are independent security gates. Setting only one is not sufficient.

---

## Auth flows

### OAuth (recommended)

1. Click **Sign in with OAuth** → new tab opens at Google consent page.
2. After consent, Google redirects to the backend callback which issues a
   one-time `auth_code` via URL fragment to `oauth-callback.html`.
3. `oauth-callback.tsx` exchanges the code (with PKCE verification) and writes
   auth state to `chrome.storage.local`, then closes the tab.
4. The popup detects the storage change and shows the home view.

### Email / Password

`POST /login/access-token` with `username` + `password` form fields. The JWT
payload is decoded locally (signature not verified) to extract display name,
email, avatar, and `exp`. Token type is `bearer`.

### API Key

`GET /profile/api-keys/verify` with `X-API-Key` header. `expires_at` is
converted from ISO 8601 to epoch ms at store time. Token type is `apikey`.
`authFetch` sends `X-API-Key` header for all subsequent requests.

> **Warning:** API keys are long-lived. Only use them from secured automation
> environments or testing. Prefer OAuth or password for interactive sessions.

---

## Session storage schema

```typescript
interface AuthState {
  accessToken: string;       // JWT (bearer) or raw API key (apikey)
  expiresAt: number;         // absolute epoch ms in all cases
  sessionId: string;         // crypto.randomUUID() — correlates concurrent events
  tokenType: "bearer" | "apikey";
  loginTimestamp: number;    // Date.now() at auth time — freshness ordering
}

interface UserProfile { name: string; email: string; avatar: string; }
```

On load, `isValidAuthState()` validates the schema; corrupt/stale data is
cleared and the login form is shown (never silently used).

---

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `VITE_API_URL` | Full API URL including prefix | `http://localhost:8000/api/v1` |
| `VITE_BACKEND_ORIGIN` | Backend origin (no path) | `http://localhost:8000` |

Copy `.env.example` to `.env.development` / `.env.production` and adjust.

---

## Algorithm compatibility

The extension is algorithm-agnostic. JWT payload is always `header.payload.signature`
(base64url-encoded) regardless of signing algorithm (HS256 / RS256 / ES256).
The extension does not cryptographically validate JWTs — it only parses the
payload segment for display.

Recommended backend config: `ACCESS_TOKEN_ALGORITHM=RS256` with `TOKEN_MODE=stateful`.

---

## Chromium-only notes

- `window.close()` for self-closing the OAuth callback tab is Chromium-guaranteed
  for tabs opened via `chrome.tabs.create()`. Firefox MV3 may require
  `chrome.tabs.remove()` instead.
- `chrome.storage.session` (per-flow PKCE verifier) is cleared on browser close.
  This is correct behaviour — incomplete OAuth flows are abandoned on restart.

---

## Threat model

| Threat | Mitigated by |
| --- | --- |
| auth_code replay | GETDEL single-use + 60 s TTL |
| auth_code interception | S256 PKCE binding — stolen code unusable without verifier |
| CSRF on OAuth redirect | `state` token in `OAuthSessionStore` |
| Auth code logged by proxy | Fragment delivery (`#auth_code=`, never in query string) |
| Concurrent flow overwrite | Per-flow `oauth_flows[flowId]` in `chrome.storage.session` |
| Stale session overwrite | `loginTimestamp` monotone ordering in storage change listener |
| Token theft after compromise | `stateful` TOKEN_MODE → immediate revocation on logout |
| API key exfiltration | Stored in `chrome.storage.local` only; never logged; UX warning |
