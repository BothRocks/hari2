import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';

export function LoginButton() {
  const { user, loading, login, logout } = useAuth();

  if (loading) {
    return <Button variant="ghost" disabled>Loading...</Button>;
  }

  if (user) {
    return (
      <div className="flex items-center gap-3">
        {user.picture && (
          <img src={user.picture} alt="" className="w-8 h-8 rounded-full" />
        )}
        <span className="text-sm">{user.name || user.email}</span>
        <Button variant="ghost" size="sm" onClick={logout}>
          Logout
        </Button>
      </div>
    );
  }

  return (
    <Button variant="default" onClick={login}>
      Login with Google
    </Button>
  );
}
