import { ComponentChildren, createContext } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import { AuthState, UserProfile, isValidAuthState } from '../types/shared_types';

export interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  tokenType: 'bearer' | 'apikey' | null;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType | null>(null);

const REFRESH_MARGIN_MS = 60_000;

// Module-level flags — prevent concurrent logout or storage-write races.
let _loggingOut = false;
let _authWriteQueue: Promise<void> = Promise.resolve();

export async function storeAuthData(
  accessToken: string,
  expiresAt: number,
  user: UserProfile,
  tokenType: 'bearer' | 'apikey',
): Promise<void> {
  _authWriteQueue = _authWriteQueue.then(async () => {
    await chrome.storage.local.set({
      auth: {
        accessToken,
        expiresAt,
        sessionId: crypto.randomUUID(),
        tokenType,
        loginTimestamp: Date.now(),
      } satisfies AuthState,
      user,
    });
  });
  return _authWriteQueue;
}

// UX-only JWT payload decode — does NOT validate signature or claims.
// Backend is the sole authority; this data is for display purposes only.
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    if (parts[1].length > 4096) return null;
    const b64 = parts[1]
      .replace(/-/g, '+')
      .replace(/_/g, '/')
      .padEnd(parts[1].length + (4 - (parts[1].length % 4)) % 4, '=');
    const payload = JSON.parse(atob(b64));
    if (typeof payload !== 'object' || payload === null) return null;
    return payload as Record<string, unknown>;
  } catch {
    return null;
  }
}

interface AuthProviderProps {
  children: ComponentChildren;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [auth, setAuth] = useState<AuthState | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);

  const loadAuth = () => {
    chrome.storage.local.get(['auth', 'user'], (stored) => {
      if (isValidAuthState(stored)) {
        setAuth(stored.auth);
        setUser(stored.user);
      } else {
        // Stale/invalid schema — clear and force re-login.
        chrome.storage.local.remove(['auth', 'user']);
        setAuth(null);
        setUser(null);
      }
    });
  };

  useEffect(() => {
    loadAuth();

    const storageListener = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string,
    ) => {
      if (area !== 'local' || !changes.auth) return;
      const incoming = changes.auth.newValue as AuthState | undefined;
      if (!incoming) {
        setAuth(null);
        setUser(null);
        return;
      }
      // Accept new auth only if it is fresher than the current session.
      setAuth((current) => {
        if (
          current &&
          typeof incoming.loginTimestamp === 'number' &&
          incoming.loginTimestamp <= current.loginTimestamp
        ) {
          return current;
        }
        return incoming;
      });
      chrome.storage.local.get('user', (s) => {
        if (s.user) setUser(s.user as UserProfile);
      });
    };

    chrome.storage.onChanged.addListener(storageListener);
    return () => chrome.storage.onChanged.removeListener(storageListener);
  }, []);

  const handleLogout = () => {
    if (_loggingOut) return;
    _loggingOut = true;
    chrome.storage.local.remove(['auth', 'user'], () => {
      setAuth(null);
      setUser(null);
      _loggingOut = false;
    });
  };

  const authFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
    if (!auth || Date.now() > auth.expiresAt - REFRESH_MARGIN_MS) {
      handleLogout();
      throw new Error('Session expired — please sign in again.');
    }

    const authHeader: Record<string, string> =
      auth.tokenType === 'apikey'
        ? { 'X-API-Key': auth.accessToken }
        : { Authorization: `Bearer ${auth.accessToken}` };

    const res = await fetch(url, {
      ...options,
      headers: { ...(options.headers as Record<string, string> | undefined ?? {}), ...authHeader },
    });

    if (res.status === 401) {
      handleLogout();
    }

    return res;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!auth,
        tokenType: auth?.tokenType ?? null,
        authFetch,
        logout: handleLogout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
