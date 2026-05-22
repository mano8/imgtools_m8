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
  const auth = s.auth as Record<string, unknown> | undefined;
  const user = s.user as Record<string, unknown> | undefined;
  return (
    typeof auth?.accessToken === 'string' &&
    typeof auth?.expiresAt === 'number' &&
    typeof auth?.sessionId === 'string' &&
    (auth?.tokenType === 'bearer' || auth?.tokenType === 'apikey') &&
    typeof auth?.loginTimestamp === 'number' &&
    typeof user?.name === 'string' &&
    typeof user?.email === 'string' &&
    typeof user?.avatar === 'string'
  );
}
