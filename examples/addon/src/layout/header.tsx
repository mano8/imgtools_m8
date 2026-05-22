import { useAuth } from '../hooks/useAuth';

export default function Header() {
  const { isAuthenticated, user } = useAuth();

  return (
    <div class="flex items-center justify-between px-4 py-3 border-b">
      <div class="flex items-center gap-2">
        <img src="/icons/icon_48.png" alt="Auth-M8" height={32} />
        <span class="font-bold text-sm">Auth-M8 Template</span>
      </div>
      {isAuthenticated && user?.email && (
        <span class="text-xs text-muted-foreground truncate max-w-[160px]">
          {user.email}
        </span>
      )}
    </div>
  );
}
