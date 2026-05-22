/**
 * OAuth callback page — runs in the browser tab opened for the OAuth redirect.
 *
 * URL layout: chrome-extension://{id}/oauth-callback.html?flow_id=X#auth_code=Y
 *   flow_id  — query param set by startOAuthLogin(); identifies the PKCE verifier.
 *   auth_code — URL fragment appended by the backend; never sent to any server.
 *
 * Flow:
 *   1. Read auth_code from fragment, flow_id from query string.
 *   2. Clear URL immediately (history.replaceState) to remove both from browser history.
 *   3. Retrieve per-flow PKCE verifier from chrome.storage.session.
 *   4. POST /exchange/ with code + verifier → receive tokens.
 *   5. Write auth state to chrome.storage.local.
 *   6. window.close() — popup detects storage change via chrome.storage.onChanged.
 */

import { getApiUrl } from './utils/utils';

const EXCHANGE_URL = getApiUrl('/google-api/exchange/');

async function getCodeVerifier(flowId: string) {
  const session = await chrome.storage.session.get('oauth_flows');
  const flows = (session.oauth_flows ?? {}) as Record<string, string>;
  const verifier = flows[flowId] ?? '';
  // Remove only this flow's verifier — concurrent flows are unaffected.
  const remaining = { ...flows };
  delete remaining[flowId];
  await chrome.storage.session.set({ oauth_flows: remaining });
  return verifier;
}

function buildAuthStorage(data: Record<string, unknown>) {
  const u = (data.user ?? {}) as Record<string, unknown>;
  return {
    auth: {
      accessToken: data.access_token as string,
      expiresAt: data.expires_at as number,
      sessionId: crypto.randomUUID(),
      tokenType: 'bearer' as const,
      loginTimestamp: Date.now(),
    },
    user: {
      name: typeof u.name === 'string' ? u.name : '',
      email: typeof u.email === 'string' ? u.email : '',
      avatar: typeof u.avatar === 'string' ? u.avatar : '',
    },
  };
}

async function exchangeAndStore(authCode: string, codeVerifier: string) {
  const res = await fetch(EXCHANGE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code: authCode, code_verifier: codeVerifier }),
  });
  if (!res.ok) return false;

  const data = (await res.json()) as Record<string, unknown>;
  if (
    typeof data.access_token !== 'string' ||
    (data.access_token as string).split('.').length !== 3
  ) {
    return false;
  }

  await chrome.storage.local.set(buildAuthStorage(data));
  return true;
}

async function handleCallback(): Promise<void> {
  const hashParams = new URLSearchParams(location.hash.slice(1));
  const authCode = hashParams.get('auth_code');
  const queryParams = new URLSearchParams(location.search);
  const flowId = queryParams.get('flow_id');

  // Clear URL immediately — removes sensitive data from browser history.
  history.replaceState({}, '', location.pathname);

  if (!authCode || !flowId) {
    window.close();
    return;
  }

  let codeVerifier = '';
  try {
    codeVerifier = await getCodeVerifier(flowId);
  } catch {
    window.close();
    return;
  }

  if (!codeVerifier) {
    window.close();
    return;
  }

  try {
    await exchangeAndStore(authCode, codeVerifier);
  } finally {
    try {
      window.close();
    } catch {
      // Firefox MV3 may not allow self-close in all contexts.
    }
    // Fallback for tabs that survive window.close() (e.g. crash-restored).
    document.body.innerHTML =
      '<p style="font-family:sans-serif;padding:2rem">Authentication complete. You may close this tab.</p>';
  }
}

handleCallback();
