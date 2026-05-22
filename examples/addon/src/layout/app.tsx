import { AuthProvider } from '../context/AuthContext';
import { useAuth } from '../hooks/useAuth';
import { Home } from './Home';
import { LoginForm } from '../components/LoginForm';
import Header from './header';

if (import.meta.env.DEV) {
  import('../dev/chromePolyfill');
}

function AppContent() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Home /> : <LoginForm />;
}

export function App() {
  return (
    <AuthProvider>
      <div class="dark max-w-[500px] m-auto">
        <Header />
        <AppContent />
      </div>
    </AuthProvider>
  );
}
