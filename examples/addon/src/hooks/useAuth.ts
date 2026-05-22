import { useContext } from 'preact/hooks';
import { AuthContext, AuthContextType } from '../context/AuthContext';

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};

export const useAuthFetch = () => useAuth().authFetch;
export const useLogout = () => useAuth().logout;
