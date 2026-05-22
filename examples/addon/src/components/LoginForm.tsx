/**
 * LoginForm — three-tab auth form (OAuth / Password / API Key).
 *
 * All three flows converge to the same chrome.storage.local write via storeAuthData().
 * The extension is a passive JWT consumer: it decodes the payload for display only.
 * The backend is the sole authorization authority.
 */

import { useState } from 'preact/hooks';
import { getApiUrl } from '../utils/utils';
import { storeAuthData, decodeJwtPayload } from '../context/AuthContext';
import { UserProfile } from '../types/shared_types';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Label } from './ui/Label';

type Tab = 'oauth' | 'password' | 'apikey';

export function LoginForm() {
  const [tab, setTab] = useState<Tab>('oauth');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  return (
    <div class="p-4 min-w-[340px]">
      <div class="flex gap-2 mb-4">
        {(['oauth', 'password', 'apikey'] as Tab[]).map((t) => (
          <button
            key={t}
            class={`px-3 py-1 rounded text-sm font-medium border ${tab === t ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}
            onClick={() => { setTab(t); setError(''); }}
          >
            {t === 'oauth' ? 'OAuth' : t === 'password' ? 'Password' : 'API Key'}
          </button>
        ))}
      </div>

      {error && <p class="text-destructive text-sm mb-3">{error}</p>}

      {tab === 'oauth' && (
        <OAuthTab onError={setError} loading={loading} setLoading={setLoading} />
      )}
      {tab === 'password' && (
        <PasswordTab onError={setError} loading={loading} setLoading={setLoading} />
      )}
      {tab === 'apikey' && (
        <ApiKeyTab onError={setError} loading={loading} setLoading={setLoading} />
      )}
    </div>
  );
}

// ── OAuth tab ──────────────────────────────────────────────────────────────────

interface TabProps {
  onError: (msg: string) => void;
  loading: boolean;
  setLoading: (v: boolean) => void;
}

function OAuthTab({ onError, loading, setLoading }: TabProps) {
  const handleOAuth = async () => {
    setLoading(true);
    try {
      const flowId = crypto.randomUUID();

      // Generate PKCE verifier (32 random bytes, base64url ≈ 43 chars — RFC 7636 §4.1).
      const raw = crypto.getRandomValues(new Uint8Array(32));
      const verifier = btoa(String.fromCharCode(...raw))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');

      // S256 challenge: base64url(sha256(verifier)).
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
      const challenge = btoa(String.fromCharCode(...new Uint8Array(digest)))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');

      // Store verifier keyed by flowId — concurrent flows don't overwrite each other.
      const existing = await chrome.storage.session.get('oauth_flows').catch(() => ({}));
      const flows = ((existing as Record<string, unknown>).oauth_flows ?? {}) as Record<string, string>;
      await chrome.storage.session.set({ oauth_flows: { ...flows, [flowId]: verifier } });

      // embed flow_id in redirect_target so oauth-callback.tsx retrieves the right verifier.
      const callbackBase = chrome.runtime.getURL('oauth-callback.html');
      const redirectTarget = `${callbackBase}?flow_id=${encodeURIComponent(flowId)}`;

      const res = await fetch(
        getApiUrl(
          `/google-api/login-url/?redirect_target=${encodeURIComponent(redirectTarget)}&code_challenge=${encodeURIComponent(challenge)}`,
        ),
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        onError((body as { detail?: string }).detail ?? 'OAuth unavailable.');
        return;
      }
      const { url } = (await res.json()) as { url: string };
      chrome.tabs.create({ url });
    } catch {
      onError('Failed to start OAuth. Check backend connectivity.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div class="flex flex-col gap-3">
      <p class="text-sm text-muted-foreground">
        Sign in via Google. A browser tab will open for consent, then close automatically.
      </p>
      <Button onClick={handleOAuth} disabled={loading}>
        {loading ? 'Opening…' : 'Sign in with OAuth'}
      </Button>
    </div>
  );
}

// ── Password tab ───────────────────────────────────────────────────────────────

function PasswordTab({ onError, loading, setLoading }: TabProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: Event) => {
    e.preventDefault();
    setLoading(true);
    try {
      const body = new URLSearchParams({ username: email, password });
      const res = await fetch(getApiUrl('/login/access-token'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        onError((data as { detail?: string }).detail ?? 'Invalid credentials.');
        return;
      }
      const data = await res.json() as { access_token: string };

      // Decode JWT payload for UX display — NOT for authorization decisions.
      const payload = decodeJwtPayload(data.access_token);
      const sub = payload?.sub;
      const exp = payload?.exp;
      if (
        typeof sub !== 'string' || !sub ||
        typeof exp !== 'number' || !isFinite(exp)
      ) {
        onError('Sign-in failed: token could not be read.');
        return;
      }

      const user: UserProfile = {
        name: typeof payload.full_name === 'string' ? payload.full_name : '',
        email: typeof payload.email === 'string' ? payload.email : '',
        avatar: typeof payload.avatar === 'string' ? payload.avatar : '',
      };
      await storeAuthData(data.access_token, exp * 1000, user, 'bearer');
    } catch {
      onError('Login failed. Check backend connectivity.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} class="flex flex-col gap-3">
      <div>
        <Label for="email">Email</Label>
        <Input
          id="email"
          type="email"
          value={email}
          onInput={(e) => setEmail((e.target as HTMLInputElement).value)}
          required
          autocomplete="username"
        />
      </div>
      <div>
        <Label for="password">Password</Label>
        <Input
          id="password"
          type="password"
          value={password}
          onInput={(e) => setPassword((e.target as HTMLInputElement).value)}
          required
          autocomplete="current-password"
        />
      </div>
      <Button type="submit" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</Button>
    </form>
  );
}

// ── API Key tab ────────────────────────────────────────────────────────────────

function ApiKeyTab({ onError, loading, setLoading }: TabProps) {
  const [apiKey, setApiKey] = useState('');

  const handleSubmit = async (e: Event) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(getApiUrl('/profile/api-keys/verify'), {
        headers: { 'X-API-Key': apiKey },
      });
      if (!res.ok) {
        onError('Invalid or expired API key.');
        return;
      }
      const data = await res.json() as { expires_at?: string };
      const expiresAt = data.expires_at
        ? new Date(data.expires_at).getTime()
        : Date.now() + 365 * 24 * 60 * 60 * 1000;

      // API key verify may not return full user profile — fall back to empty strings.
      const user: UserProfile = { name: '', email: '', avatar: '' };
      await storeAuthData(apiKey, expiresAt, user, 'apikey');
    } catch {
      onError('Verification failed. Check backend connectivity.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} class="flex flex-col gap-3">
      <p class="text-xs text-amber-600 dark:text-amber-400 border border-amber-400 rounded p-2">
        ⚠ API keys are long-lived credentials stored in chrome.storage.local.
        Prefer OAuth or password for interactive use. Use API keys only from
        secured automation environments.
      </p>
      <div>
        <Label for="apikey">API Key</Label>
        <Input
          id="apikey"
          type="password"
          value={apiKey}
          onInput={(e) => setApiKey((e.target as HTMLInputElement).value)}
          required
          autocomplete="off"
          placeholder="paste your API key"
        />
      </div>
      <Button type="submit" disabled={loading}>{loading ? 'Verifying…' : 'Use API Key'}</Button>
    </form>
  );
}
