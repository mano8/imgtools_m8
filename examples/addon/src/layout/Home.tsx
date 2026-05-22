/**
 * Home — authenticated view.
 *
 * Shows user info and a "Test API" button that calls the appropriate endpoint
 * based on tokenType (bearer → GET /profile/get/me/, apikey → GET /profile/api-keys/verify).
 */

import { useState } from 'preact/hooks';
import { getApiUrl } from '../utils/utils';
import { useAuth } from '../hooks/useAuth';
import { Button } from '../components/ui/Button';

export function Home() {
  const { user, tokenType, authFetch, logout } = useAuth();
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  const testEndpoint =
    tokenType === 'apikey'
      ? getApiUrl('/profile/api-keys/verify')
      : getApiUrl('/profile/get/me/');

  const handleTestApi = async () => {
    setLoading(true);
    setResult('');
    try {
      const res = await authFetch(testEndpoint);
      const data = await res.json();
      setResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setResult(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div class="p-4 min-w-[340px] flex flex-col gap-4">
      <div class="flex items-center gap-3">
        {user?.avatar && (
          <img src={user.avatar} alt="" width={40} height={40} class="w-10 h-10 rounded-full" />
        )}
        <div>
          <p class="font-semibold">{user?.name || '—'}</p>
          <p class="text-sm text-muted-foreground">{user?.email || '—'}</p>
        </div>
      </div>

      {tokenType === 'apikey' && (
        <p class="text-xs text-amber-600 dark:text-amber-400">Signed in with API Key</p>
      )}

      <div class="flex gap-2">
        <Button onClick={handleTestApi} disabled={loading} class="flex-1">
          {loading ? 'Testing…' : 'Test API'}
        </Button>
        <Button variant="outline" onClick={logout}>Logout</Button>
      </div>

      {result && (
        <pre class="text-xs bg-muted rounded p-2 overflow-auto max-h-60 whitespace-pre-wrap">
          {result}
        </pre>
      )}
    </div>
  );
}
