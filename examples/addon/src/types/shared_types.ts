export interface UserProfile {
  name: string;
  email: string;
  avatar: string;
}

export interface AuthState {
  accessToken: string;
  expiresAt: number;      // absolute epoch ms in all cases
  sessionId: string;
  tokenType: 'bearer' | 'apikey';
  loginTimestamp: number; // Date.now() at auth time — used for stale-session ordering
}

export interface AuthStorage {
  auth: AuthState;
  user: UserProfile;
}

export function isValidAuthState(v: unknown): v is AuthStorage {
  if (typeof v !== 'object' || v === null) return false;
  const s = v as Record<string, unknown>;
  const a = s.auth as Record<string, unknown> | undefined;
  const u = s.user as Record<string, unknown> | undefined;
  const tokenTypeOk = a?.tokenType === 'bearer' || a?.tokenType === 'apikey';
  return [
    typeof a?.accessToken === 'string',
    typeof a?.expiresAt === 'number',
    typeof a?.sessionId === 'string',
    tokenTypeOk,
    typeof a?.loginTimestamp === 'number',
    typeof u?.name === 'string',
    typeof u?.email === 'string',
    typeof u?.avatar === 'string',
  ].every(Boolean);
}
