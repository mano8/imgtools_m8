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

  // Retrieve per-flow PKCE verifier then clean up only this flow's entry.
  let codeVerifier = '';
  try {
    const session = await chrome.storage.session.get('oauth_flows');
    const flows = (session.oauth_flows ?? {}) as Record<string, string>;
    codeVerifier = flows[flowId] ?? '';
    const { [flowId]: _removed, ...remaining } = flows;
    await chrome.storage.session.set({ oauth_flows: remaining });
  } catch {
    window.close();
    return;
  }

  if (!codeVerifier) {
    window.close();
    return;
  }

  try {
    const res = await fetch(EXCHANGE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: authCode, code_verifier: codeVerifier }),
    });

    if (!res.ok) {
      window.close();
      return;
    }

    const data = await res.json();

    // Reject structurally invalid JWTs before storing.
    if (
      typeof data.access_token !== 'string' ||
      data.access_token.split('.').length !== 3
    ) {
      window.close();
      return;
    }

    await chrome.storage.local.set({
      auth: {
        accessToken: data.access_token,
        expiresAt: data.expires_at,
        sessionId: crypto.randomUUID(),
        tokenType: 'bearer',
        loginTimestamp: Date.now(),
      },
      user: {
        name: data.user?.name ?? '',
        email: data.user?.email ?? '',
        avatar: data.user?.avatar ?? '',
      },
    });
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
